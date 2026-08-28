from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import timedelta
from pathlib import PurePosixPath
from typing import Iterable

from .capabilities import Capability, CapabilitySigner
from .clock import Clock
from .errors import Conflict, Expired, Forbidden, IntegrityFailure, ValidationError
from .ids import new_id
from .memory import MemoryObjectStore, MemoryStore
from .models import (
    ActorContext,
    Document,
    DocumentRequest,
    DocumentState,
    OutboxMessage,
    Receipt,
    Role,
    ScanResult,
    SupportRequest,
    UploadSession,
    UploadState,
)
from .scanning import ScanPipeline
from .scope import require_entity, require_household, require_role, require_step_up


@dataclass(frozen=True)
class UploadPolicy:
    max_document_bytes: int = 25 * 1024 * 1024
    max_part_bytes: int = 8 * 1024 * 1024
    upload_ttl: timedelta = timedelta(hours=2)
    capability_ttl: timedelta = timedelta(minutes=5)
    download_ttl: timedelta = timedelta(seconds=60)
    allowed_declared_types: frozenset[str] = frozenset(
        {"application/pdf", "image/jpeg", "image/png", "text/plain", "text/csv", "application/csv"}
    )
    allowed_extensions: frozenset[str] = frozenset({".pdf", ".jpg", ".jpeg", ".png", ".txt", ".csv"})


@dataclass(frozen=True)
class UploadStart:
    document: Document
    upload: UploadSession


class UploadService:
    QUARANTINE_BUCKET = "quarantine"
    CLEAN_BUCKET = "clean"

    def __init__(
        self,
        *,
        store: MemoryStore,
        objects: MemoryObjectStore,
        capabilities: CapabilitySigner,
        clock: Clock,
        policy: UploadPolicy | None = None,
    ) -> None:
        self.store = store
        self.objects = objects
        self.capabilities = capabilities
        self.clock = clock
        self.policy = policy or UploadPolicy()

    @staticmethod
    def _safe_display_filename(filename: str) -> str:
        value = filename.strip().replace("\\", "/").split("/")[-1]
        value = re.sub(r"[\x00-\x1f\x7f]", "", value)
        if not value or len(value) > 180:
            raise ValidationError("invalid filename")
        return value

    @staticmethod
    def _private_key(prefix: str, household_id: str, document_id: str) -> str:
        key = f"{prefix}/{household_id}/{document_id}/{new_id()}"
        path = PurePosixPath(key)
        if path.is_absolute() or ".." in path.parts:
            raise AssertionError("generated object key is unsafe")
        return key

    def create_document_request(
        self,
        *,
        advisor: ActorContext,
        household_id: str,
        entity_id: str | None,
        title: str,
        description: str,
        due_at: object | None,
    ) -> DocumentRequest:
        now = self.clock.now()
        require_role(advisor, Role.ADVISOR, Role.OPERATIONS, household_id=household_id)
        require_entity(advisor, household_id, entity_id)
        if not title.strip() or len(title) > 160 or len(description) > 2_000:
            raise ValidationError("invalid document request")
        row = DocumentRequest(
            id=new_id(),
            household_id=household_id,
            entity_id=entity_id,
            title=title.strip(),
            description=description.strip(),
            due_at=due_at,
            created_by=advisor.user_id,
            created_at=now,
        )
        self.store.document_requests[row.id] = row
        self.store.audit(
            at=now,
            actor_id=advisor.user_id,
            action="document.request.created",
            object_id=row.id,
            detail={"household_id": household_id, "entity_id": entity_id},
        )
        return row

    def begin_upload(
        self,
        *,
        actor: ActorContext,
        request_id: str,
        filename: str,
        declared_content_type: str,
        declared_size: int,
        idempotency_key: str,
    ) -> UploadStart:
        now = self.clock.now()
        request = self.store.require_document_request(request_id)
        require_entity(actor, request.household_id, request.entity_id)
        require_role(
            actor, Role.CLIENT, Role.ADVISOR, Role.OPERATIONS, household_id=request.household_id
        )
        if declared_content_type not in self.policy.allowed_declared_types:
            raise ValidationError("declared content type is not allowed")
        if declared_size <= 0 or declared_size > self.policy.max_document_bytes:
            raise ValidationError("document size is outside policy")
        safe_name = self._safe_display_filename(filename)
        suffix = PurePosixPath(safe_name).suffix.lower()
        if suffix not in self.policy.allowed_extensions:
            raise ValidationError("file extension is not allowed")
        if not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", idempotency_key):
            raise ValidationError("invalid idempotency key")
        existing_id = self.store.idempotent_object("upload.begin", actor.user_id, idempotency_key)
        if existing_id:
            upload = self.store.require_upload(existing_id)
            return UploadStart(self.store.require_document(upload.document_id), upload)

        document_id = new_id()
        qkey = self._private_key("quarantine", request.household_id, document_id)
        multipart_id = self.objects.create_multipart(bucket=self.QUARANTINE_BUCKET, key=qkey)
        document = Document(
            id=document_id,
            household_id=request.household_id,
            entity_id=request.entity_id,
            request_id=request.id,
            uploaded_by=actor.user_id,
            original_filename=safe_name,
            declared_content_type=declared_content_type,
            authoritative_content_type=None,
            authoritative_size=None,
            authoritative_sha256=None,
            quarantine_key=qkey,
            clean_key=None,
            state=DocumentState.UPLOADING,
            created_at=now,
            updated_at=now,
        )
        upload = UploadSession(
            id=new_id(),
            document_id=document.id,
            household_id=request.household_id,
            object_key=qkey,
            declared_size=declared_size,
            multipart_upload_id=multipart_id,
            idempotency_key=idempotency_key,
            created_at=now,
            expires_at=now + self.policy.upload_ttl,
        )
        self.store.documents[document.id] = document
        self.store.uploads[upload.id] = upload
        self.store.remember_idempotency("upload.begin", actor.user_id, idempotency_key, upload.id)
        return UploadStart(document, upload)

    def sign_upload_part(self, *, actor: ActorContext, upload_id: str, part_number: int) -> Capability:
        now = self.clock.now()
        upload = self.store.require_upload(upload_id)
        document = self.store.require_document(upload.document_id)
        require_household(actor, upload.household_id)
        if document.uploaded_by != actor.user_id:
            raise Forbidden("upload belongs to another portal user")
        if upload.expires_at <= now:
            upload.state = UploadState.EXPIRED
            raise Expired("upload session expired")
        if upload.state is not UploadState.OPEN:
            raise Conflict("upload is not open")
        if part_number < 1 or part_number > 10_000:
            raise ValidationError("invalid part number")
        return self.capabilities.issue(
            now=now,
            actor_id=actor.user_id,
            household_id=upload.household_id,
            resource_id=upload.id,
            bucket=self.QUARANTINE_BUCKET,
            object_key=document.quarantine_key,
            method="PUT",
            ttl=self.policy.capability_ttl,
            max_bytes=self.policy.max_part_bytes,
            part_number=part_number,
        )

    def upload_part(
        self,
        *,
        actor: ActorContext,
        upload_id: str,
        part_number: int,
        capability: str,
        data: bytes,
    ) -> str:
        now = self.clock.now()
        upload = self.store.require_upload(upload_id)
        document = self.store.require_document(upload.document_id)
        require_household(actor, upload.household_id)
        if document.uploaded_by != actor.user_id:
            raise Forbidden("upload belongs to another portal user")
        if upload.expires_at <= now:
            upload.state = UploadState.EXPIRED
            raise Expired("upload session expired")
        if not data or len(data) > self.policy.max_part_bytes:
            raise ValidationError("part size is outside policy")
        self.capabilities.verify(
            capability,
            now=now,
            actor_id=actor.user_id,
            household_id=upload.household_id,
            resource_id=upload.id,
            bucket=self.QUARANTINE_BUCKET,
            object_key=document.quarantine_key,
            method="PUT",
            content_length=len(data),
            part_number=part_number,
        )
        etag = self.objects.put_part(upload.multipart_upload_id, part_number, data)
        previous = upload.completed_parts.get(part_number)
        if previous is None:
            upload.uploaded_bytes += len(data)
        else:
            sizes = self.objects.list_parts(upload.multipart_upload_id)
            upload.uploaded_bytes = sum(sizes.values())
        upload.completed_parts[part_number] = etag
        if upload.uploaded_bytes > upload.declared_size or upload.uploaded_bytes > self.policy.max_document_bytes:
            self.abort_upload(actor=actor, upload_id=upload.id, reason="declared size exceeded")
            raise IntegrityFailure("uploaded bytes exceed declared or allowed size")
        document.updated_at = now
        return etag

    def resume_upload(self, *, actor: ActorContext, upload_id: str) -> dict[str, object]:
        now = self.clock.now()
        upload = self.store.require_upload(upload_id)
        require_household(actor, upload.household_id)
        document = self.store.require_document(upload.document_id)
        if document.uploaded_by != actor.user_id:
            raise Forbidden("upload belongs to another portal user")
        if upload.expires_at <= now:
            upload.state = UploadState.EXPIRED
        return {
            "upload_id": upload.id,
            "state": upload.state.value,
            "declared_size": upload.declared_size,
            "uploaded_bytes": upload.uploaded_bytes,
            "parts": self.objects.list_parts(upload.multipart_upload_id)
            if upload.state is UploadState.OPEN
            else {},
            "expires_at": upload.expires_at.isoformat(),
        }

    def complete_upload(self, *, actor: ActorContext, upload_id: str, ordered_parts: list[int]) -> Document:
        now = self.clock.now()
        upload = self.store.require_upload(upload_id)
        document = self.store.require_document(upload.document_id)
        require_household(actor, upload.household_id)
        if document.uploaded_by != actor.user_id:
            raise Forbidden("upload belongs to another portal user")
        if upload.expires_at <= now:
            upload.state = UploadState.EXPIRED
            raise Expired("upload session expired")
        if upload.state is not UploadState.OPEN:
            raise Conflict("upload cannot be completed from current state")
        _, _, size = self.objects.complete_multipart(upload.multipart_upload_id, ordered_parts)
        upload.state = UploadState.OBJECT_COMPLETE
        if size != upload.declared_size or size <= 0 or size > self.policy.max_document_bytes:
            self.objects.delete(bucket=self.QUARANTINE_BUCKET, key=document.quarantine_key)
            upload.state = UploadState.ABORTED
            document.state = DocumentState.REJECTED
            document.review_note = "authoritative object size did not match declaration"
            raise IntegrityFailure("authoritative object size mismatch")
        body = self.objects.get(bucket=self.QUARANTINE_BUCKET, key=document.quarantine_key)
        digest = hashlib.sha256(body).hexdigest()
        document.authoritative_size = size
        document.authoritative_sha256 = digest
        document.state = DocumentState.QUARANTINED
        document.updated_at = now
        upload.uploaded_bytes = size
        upload.state = UploadState.SCAN_QUEUED

        duplicate = next(
            (
                row
                for row in self.store.documents.values()
                if row.id != document.id
                and row.household_id == document.household_id
                and row.authoritative_sha256 == digest
                and row.authoritative_size == size
                and row.state
                in {DocumentState.READY_FOR_REVIEW, DocumentState.ACCEPTED, DocumentState.DUPLICATE}
            ),
            None,
        )
        if duplicate is not None:
            document.state = DocumentState.DUPLICATE
            document.duplicate_of = duplicate.id
            upload.state = UploadState.COMPLETE
            self.objects.delete(bucket=self.QUARANTINE_BUCKET, key=document.quarantine_key)
            self._receipt(
                document=document,
                event_type="document.duplicate_detected",
                actor_id=actor.user_id,
                payload={"duplicate_of": duplicate.id, "sha256": digest, "size": size},
            )
            return document

        self.store.outbox.append(
            OutboxMessage(
                id=new_id(),
                channel="worker",
                topic="document.scan_requested",
                aggregate_id=document.id,
                payload={"document_id": document.id, "quarantine_key": document.quarantine_key},
                created_at=now,
                available_at=now,
            )
        )
        return document

    def scan_document(self, *, document_id: str, scanner: ScanPipeline, worker_id: str = "scanner") -> ScanResult:
        now = self.clock.now()
        document = self.store.require_document(document_id)
        if document.state is not DocumentState.QUARANTINED:
            raise Conflict("document is not awaiting scan")
        document.state = DocumentState.SCANNING
        document.updated_at = now
        body = self.objects.get(bucket=self.QUARANTINE_BUCKET, key=document.quarantine_key)
        try:
            result = scanner.scan(data=body, filename=document.original_filename)
        except Exception as exc:
            document.state = DocumentState.QUARANTINED
            document.review_note = f"scan unavailable: {type(exc).__name__}"
            document.updated_at = now
            raise
        if not result.clean:
            document.state = DocumentState.REJECTED
            document.authoritative_content_type = result.mime_type
            document.review_note = result.reason
            document.updated_at = now
            self._receipt(
                document=document,
                event_type="document.scan_rejected",
                actor_id=worker_id,
                payload={
                    "sha256": document.authoritative_sha256,
                    "size": document.authoritative_size,
                    "mime": result.mime_type,
                    "reason": result.reason,
                    "findings": [asdict(item) for item in result.findings],
                },
            )
            return result

        clean_key = self._private_key("clean", document.household_id, document.id)
        self.objects.copy(
            source_bucket=self.QUARANTINE_BUCKET,
            source_key=document.quarantine_key,
            target_bucket=self.CLEAN_BUCKET,
            target_key=clean_key,
        )
        copied = self.objects.get(bucket=self.CLEAN_BUCKET, key=clean_key)
        copied_digest = hashlib.sha256(copied).hexdigest()
        if copied_digest != document.authoritative_sha256 or len(copied) != document.authoritative_size:
            self.objects.delete(bucket=self.CLEAN_BUCKET, key=clean_key)
            document.state = DocumentState.QUARANTINED
            raise IntegrityFailure("clean-store copy verification failed")
        self.objects.delete(bucket=self.QUARANTINE_BUCKET, key=document.quarantine_key)
        document.clean_key = clean_key
        document.authoritative_content_type = result.mime_type
        document.state = DocumentState.READY_FOR_REVIEW
        document.updated_at = now
        upload = next(row for row in self.store.uploads.values() if row.document_id == document.id)
        upload.state = UploadState.COMPLETE
        self._receipt(
            document=document,
            event_type="document.clean_stored",
            actor_id=worker_id,
            payload={
                "sha256": document.authoritative_sha256,
                "size": document.authoritative_size,
                "mime": result.mime_type,
                "clean_key": clean_key,
                "findings": [asdict(item) for item in result.findings],
            },
        )
        return result

    def review_document(
        self,
        *,
        advisor: ActorContext,
        document_id: str,
        decision: str,
        note: str = "",
    ) -> Document:
        now = self.clock.now()
        document = self.store.require_document(document_id)
        require_role(
            advisor, Role.ADVISOR, Role.OPERATIONS, household_id=document.household_id
        )
        require_entity(advisor, document.household_id, document.entity_id)
        if document.state not in {DocumentState.READY_FOR_REVIEW, DocumentState.NEEDS_REPLACEMENT}:
            raise Conflict("document is not reviewable")
        mapping = {
            "accept": DocumentState.ACCEPTED,
            "replace": DocumentState.NEEDS_REPLACEMENT,
            "reject": DocumentState.REJECTED,
        }
        if decision not in mapping:
            raise ValidationError("invalid review decision")
        document.state = mapping[decision]
        document.review_note = note[:1_000]
        document.updated_at = now
        request = self.store.require_document_request(document.request_id)
        request.status = "complete" if decision == "accept" else "missing" if decision == "replace" else "reviewed"
        self._receipt(
            document=document,
            event_type=f"document.review.{decision}",
            actor_id=advisor.user_id,
            payload={"note": document.review_note},
        )
        if decision == "accept":
            self.store.outbox.append(
                OutboxMessage(
                    id=new_id(),
                    channel="mas_intake",
                    topic="mas.document.accepted",
                    aggregate_id=document.id,
                    payload={
                        "direction": "outbound_only",
                        "document_id": document.id,
                        "household_id": document.household_id,
                        "entity_id": document.entity_id,
                        "sha256": document.authoritative_sha256,
                        "size": document.authoritative_size,
                        "content_type": document.authoritative_content_type,
                    },
                    created_at=now,
                    available_at=now,
                )
            )
        return document

    def sign_download(self, *, advisor: ActorContext, document_id: str) -> Capability:
        now = self.clock.now()
        document = self.store.require_document(document_id)
        require_role(
            advisor, Role.ADVISOR, Role.OPERATIONS, household_id=document.household_id
        )
        require_step_up(advisor, now=now)
        require_entity(advisor, document.household_id, document.entity_id)
        if document.state not in {DocumentState.READY_FOR_REVIEW, DocumentState.ACCEPTED} or not document.clean_key:
            raise Conflict("document is not available for download")
        return self.capabilities.issue(
            now=now,
            actor_id=advisor.user_id,
            household_id=document.household_id,
            resource_id=document.id,
            bucket=self.CLEAN_BUCKET,
            object_key=document.clean_key,
            method="GET",
            ttl=self.policy.download_ttl,
        )

    def delete_document(self, *, advisor: ActorContext, document_id: str, reason: str) -> Document:
        now = self.clock.now()
        document = self.store.require_document(document_id)
        require_role(advisor, Role.ADVISOR, household_id=document.household_id)
        require_step_up(advisor, now=now)
        require_entity(advisor, document.household_id, document.entity_id)
        if document.state is DocumentState.DELETED:
            return document
        previous = document.state.value
        if document.clean_key:
            self.objects.delete(bucket=self.CLEAN_BUCKET, key=document.clean_key)
        self.objects.delete(bucket=self.QUARANTINE_BUCKET, key=document.quarantine_key)
        document.state = DocumentState.DELETED
        document.deleted_at = now
        document.updated_at = now
        document.review_note = reason[:1_000]
        self._receipt(
            document=document,
            event_type="document.deleted",
            actor_id=advisor.user_id,
            payload={"previous_state": previous, "reason": document.review_note},
        )
        return document

    def abort_upload(self, *, actor: ActorContext, upload_id: str, reason: str) -> None:
        now = self.clock.now()
        upload = self.store.require_upload(upload_id)
        require_household(actor, upload.household_id)
        document = self.store.require_document(upload.document_id)
        if document.uploaded_by != actor.user_id:
            raise Forbidden("upload belongs to another portal user")
        if upload.state is UploadState.OPEN:
            self.objects.abort_multipart(upload.multipart_upload_id)
        self.objects.delete(bucket=self.QUARANTINE_BUCKET, key=upload.object_key)
        upload.state = UploadState.ABORTED
        document.state = DocumentState.REJECTED
        document.review_note = reason[:500]
        document.updated_at = now

    def open_support_request(self, *, client: ActorContext, message: str) -> SupportRequest:
        now = self.clock.now()
        client_households = sorted(
            household_id
            for household_id in client.household_ids
            if (household_id, Role.CLIENT) in client.role_scope
        )
        if not client_households:
            raise Forbidden("client role is required")
        if not message.strip() or len(message.strip()) > 500:
            raise ValidationError("support message must be 1-500 characters")
        household_id = client_households[0]
        row = SupportRequest(
            id=new_id(),
            household_id=household_id,
            created_by=client.user_id,
            category="portal_document_support",
            message=message.strip(),
            created_at=now,
        )
        self.store.support_requests[row.id] = row
        self.store.outbox.append(
            OutboxMessage(
                id=new_id(),
                channel="advisor_queue",
                topic="portal.support.requested",
                aggregate_id=row.id,
                payload={"support_request_id": row.id, "household_id": household_id},
                created_at=now,
                available_at=now,
            )
        )
        return row

    def _receipt(self, *, document: Document, event_type: str, actor_id: str, payload: dict[str, object]) -> Receipt:
        now = self.clock.now()
        receipt_id = new_id()
        canonical = json.dumps(
            {
                "id": receipt_id,
                "household_id": document.household_id,
                "document_id": document.id,
                "event_type": event_type,
                "event_at": now.isoformat(),
                "actor_id": actor_id,
                "payload": payload,
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode()
        row = Receipt(
            id=receipt_id,
            household_id=document.household_id,
            document_id=document.id,
            event_type=event_type,
            event_at=now,
            actor_id=actor_id,
            payload=dict(payload),
            receipt_sha256=hashlib.sha256(canonical).hexdigest(),
        )
        self.store.receipts.append(row)
        return row
