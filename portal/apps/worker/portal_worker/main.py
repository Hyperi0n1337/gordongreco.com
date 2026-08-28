from __future__ import annotations

import hashlib
import json
import logging
import os
import signal
import tempfile
import time
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from portal_adapters.postgres import PortalDatabase
from portal_adapters.s3 import S3PrivateObjectStore
from portal_adapters.scanners import ClamAvScanner, LibmagicDetector, QpdfValidator
from portal_core.scanning import ScanPipeline

log = logging.getLogger("portal_worker")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")


class Worker:
    def __init__(self) -> None:
        self.db = PortalDatabase(os.environ["DATABASE_URL"], min_size=1, max_size=5)
        self.quarantine_bucket = os.getenv("QUARANTINE_BUCKET", "gg-portal-quarantine")
        self.clean_bucket = os.getenv("CLEAN_BUCKET", "gg-portal-clean")
        self.max_bytes = int(os.getenv("MAX_DOCUMENT_BYTES", str(25 * 1024 * 1024)))
        self.s3 = S3PrivateObjectStore(
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            endpoint_url=os.getenv("S3_ENDPOINT_URL") or None,
            kms_key_id=os.getenv("KMS_KEY_ID") or None,
        )
        self.scanner = ScanPipeline(
            magic=LibmagicDetector(os.getenv("MAGIC_COMMAND", "/usr/bin/file")),
            malware=ClamAvScanner(os.getenv("CLAMAV_COMMAND", "/usr/bin/clamdscan")),
            pdf=QpdfValidator(os.getenv("QPDF_COMMAND", "/usr/bin/qpdf")),
        )
        self.mas_intake_dir = Path(os.getenv("MAS_INTAKE_DIR", "/var/lib/mas-intake/outbound"))
        self.stop_requested = False

    def stop(self, *_: object) -> None:
        self.stop_requested = True

    def run(self) -> None:
        self.db.open()
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        try:
            while not self.stop_requested:
                handled = self.scan_once() or self.delete_once() or self.outbox_once() or self.recalculate_once()
                if not handled:
                    time.sleep(1.0)
        finally:
            self.db.close()

    def scan_once(self) -> bool:
        with self.db.worker_transaction("document-scanner") as conn:
            job = conn.execute("SELECT * FROM portal.worker_claim_scan_job()").fetchone()
            if not job:
                return False
            try:
                data = self.s3.read(
                    bucket=self.quarantine_bucket,
                    key=job["quarantine_key"],
                    max_bytes=self.max_bytes,
                )
                digest = hashlib.sha256(data).hexdigest()
                if digest != job["authoritative_sha256"] or len(data) != job["authoritative_size"]:
                    raise ValueError("quarantine object differs from authoritative hash or size")
                result = self.scanner.scan(data=data, filename=job["original_filename"])
                if not result.clean:
                    conn.execute(
                        "SELECT portal.worker_reject_document(%s,%s,%s,%s)",
                        (
                            job["document_id"],
                            result.mime_type,
                            result.reason,
                            [asdict(item) for item in result.findings],
                        ),
                    )
                    return True
                clean_key = f"clean/{job['household_id']}/{job['document_id']}/{__import__('uuid').uuid4()}"
                self.s3.copy_verified(
                    source_bucket=self.quarantine_bucket,
                    source_key=job["quarantine_key"],
                    target_bucket=self.clean_bucket,
                    target_key=clean_key,
                    authoritative_sha256=digest,
                    authoritative_size=len(data),
                    content_type=result.mime_type,
                )
                conn.execute(
                    "SELECT portal.worker_accept_document(%s,%s,%s,%s)",
                    (
                        job["document_id"],
                        result.mime_type,
                        clean_key,
                        [asdict(item) for item in result.findings],
                    ),
                )
                self.s3.delete(bucket=self.quarantine_bucket, key=job["quarantine_key"])
            except Exception as exc:
                log.exception("scan failed closed for document %s", job["document_id"])
                conn.execute(
                    "SELECT portal.worker_retry_scan(%s,%s)",
                    (job["document_id"], f"{type(exc).__name__}: {str(exc)[:300]}"),
                )
            return True

    def delete_once(self) -> bool:
        with self.db.worker_transaction("object-deleter") as conn:
            job = conn.execute("SELECT * FROM portal.worker_claim_delete_job()").fetchone()
            if not job:
                return False
            try:
                if job["clean_key"]:
                    self.s3.delete(bucket=self.clean_bucket, key=job["clean_key"])
                if job["quarantine_key"]:
                    self.s3.delete(bucket=self.quarantine_bucket, key=job["quarantine_key"])
                conn.execute("SELECT portal.worker_complete_delete(%s)", (job["document_id"],))
            except Exception as exc:
                conn.execute(
                    "SELECT portal.worker_retry_delete(%s,%s)",
                    (job["document_id"], f"{type(exc).__name__}: {str(exc)[:300]}"),
                )
            return True

    def outbox_once(self) -> bool:
        with self.db.worker_transaction("outbox-dispatcher") as conn:
            job = conn.execute("SELECT * FROM portal.worker_claim_outbox()").fetchone()
            if not job:
                return False
            try:
                channel = job["channel"]
                if channel in {"mas_intake", "telegram", "email", "advisor_queue"}:
                    self._write_outbound_only(job)
                elif channel == "worker":
                    # Scan jobs are claimed by worker_claim_scan_job, never dispatched externally.
                    conn.execute("SELECT portal.worker_release_outbox(%s)", (job["id"],))
                    return True
                else:
                    raise ValueError(f"unknown outbox channel: {channel}")
                conn.execute("SELECT portal.worker_complete_outbox(%s)", (job["id"],))
            except Exception as exc:
                conn.execute(
                    "SELECT portal.worker_retry_outbox(%s,%s)",
                    (job["id"], f"{type(exc).__name__}: {str(exc)[:300]}"),
                )
            return True

    def recalculate_once(self) -> bool:
        with self.db.worker_transaction("recalculation-dispatcher") as conn:
            job = conn.execute("SELECT * FROM portal.worker_claim_recalculation()").fetchone()
            if not job:
                return False
            try:
                payload = {
                    "schema_version": "mas.portal.recalculation_intake.v1",
                    "direction": "outbound_only",
                    "job_id": str(job["id"]),
                    "household_id": str(job["household_id"]),
                    "reason": job["reason"],
                    "source_id": str(job["source_id"]),
                    "requested_at": job["requested_at"].isoformat(),
                    "trade": "none",
                    "money_movement": "none",
                }
                self._atomic_json(self.mas_intake_dir / "recalculation" / f"{job['id']}.json", payload)
                conn.execute("SELECT portal.worker_complete_recalculation(%s)", (job["id"],))
            except Exception as exc:
                conn.execute(
                    "SELECT portal.worker_retry_recalculation(%s,%s)",
                    (job["id"], f"{type(exc).__name__}: {str(exc)[:300]}"),
                )
            return True

    def _write_outbound_only(self, row: dict[str, Any]) -> None:
        payload = {
            "schema_version": "mas.portal.outbound_envelope.v1",
            "direction": "outbound_only",
            "outbox_id": str(row["id"]),
            "channel": row["channel"],
            "topic": row["topic"],
            "aggregate_id": str(row["aggregate_id"]),
            "created_at": row["created_at"].isoformat(),
            "payload": row["payload"],
        }
        if row.get("secret_ciphertext"):
            payload["sealed_secret_ciphertext"] = row["secret_ciphertext"]
        self._atomic_json(self.mas_intake_dir / row["channel"] / f"{row['id']}.json", payload)

    @staticmethod
    def _atomic_json(target: Path, payload: dict[str, Any]) -> None:
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        raw = (json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str) + "\n").encode()
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".pending-", delete=False) as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
            temp = Path(handle.name)
        os.chmod(temp, 0o600)
        temp.replace(target)


if __name__ == "__main__":
    Worker().run()
