#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {"implementation_manifest.json"}
entries = []
for path in sorted(ROOT.rglob("*")):
    if not path.is_file() or path.is_symlink():
        continue
    rel = path.relative_to(ROOT).as_posix()
    if rel in EXCLUDED or rel.startswith((".git/", ".wrangler/")) or "/__pycache__/" in f"/{rel}/" or rel.startswith("verification/logs/"):
        continue
    body = path.read_bytes()
    entries.append({"path": rel, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()})
manifest = {
    "schema_version": "mas.implementation_manifest.v1",
    "prompt_id": "MAS-RP-402",
    "identity_marker": "MAS-RP-402-SECURE-PORTAL-ACTUAL-ZIP",
    "artifact_root": ROOT.name,
    "data_class": "private_design_context_no_client_documents",
    "authority_boundary": "code_and_verification_only_no_deployment_credentials_real_client_data_account_creation_message_send_trade_or_money_movement",
    "source_file_count": len(entries),
    "source_bytes": sum(item["bytes"] for item in entries),
    "files": entries,
    "manifest_exclusions": ["implementation_manifest.json (self)", ".git/*", "__pycache__/*"],
    "verification_command": "python scripts/verify.py --no-write",
}
(ROOT / "implementation_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"wrote implementation_manifest.json: {len(entries)} files, {manifest['source_bytes']} bytes")
