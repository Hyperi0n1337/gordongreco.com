# Threat model

## Protected assets

Authentication factors, session authority, household/entity scope, requested and uploaded document metadata, quarantined and clean document bytes, immutable receipts, treasury policy versions, approvals, cash-operation requests, and outbound intake envelopes.

## Primary threats and implemented controls

| Threat | Control | Verification |
|---|---|---|
| Password reuse, credential stuffing | No password endpoint; invitation-only one-time magic links; generic request response; rate-limit RPC. | `tests/test_auth.py`, migration 0006. |
| Session theft or fixation | Random opaque token; HMAC digest at rest; secure/HttpOnly/Strict cookie; rotation at login; expiry; auth epoch; logout/revocation. | Auth tests and API cookie code. |
| CSRF / cross-origin mutation | Exact origin allowlist; CSRF cookie/header equality; no wildcard CORS; JSON-only mutation APIs except bounded binary part PUT. | `http_security.py`, UI/API tests. |
| Horizontal privilege escalation | Server-derived household/entity pairs and per-household roles; forced RLS; no direct table writes. | Scope tests and migration tests. |
| Advisor authority bleeding across households | `role_scope` pairs and `has_household_role`; every privileged RPC checks target household. | `test_role_is_derived_per_household...`. |
| User-controlled object key traversal | Random server-generated keys; filenames stored only as sanitized display metadata. | Upload tests and SQL constraints. |
| Oversized, partial, reordered, or duplicate upload | Declared and authoritative limits; ordered unique parts; idempotency; resume status; SHA-256; duplicate state and redundant-object deletion. | Upload tests. |
| Polyglot/executable/malicious upload | Signature checks before MIME; fail-closed libmagic; extension/MIME mapping; blocked active PDF markers; qpdf; ClamAV. | Scanning tests. |
| Quarantine bypass | Worker-only state transitions; private buckets; clean copy only after pass; copy hash/size verification. | Upload service, worker RPCs. |
| Signed URL/capability widening | HMAC capability binds actor, household, resource, bucket, key, method, part, maximum bytes, and expiry; maximum TTL ten minutes. | Capability tests. |
| Receipt or approval rewriting | Receipt hash; append-only triggers; workflow approvals immutable; narrow revision-aware RPCs. | Migration 0009 and receipt tests. |
| Treasury request interpreted as execution | `execution_state='not_executable'`; allowed operation vocabulary; designated signers; advisor approval; outbound-only envelopes with explicit `trade`, `money_movement`, and `execution` set to `none`. | Treasury tests. |
| Duplicate/conflicting financial request | Idempotency keys, unique conflict key for active operations, expected revision, stale base rejection, one pending amendment per base. | Treasury tests and migration constraints. |
| Worker compromise | Separate NOINHERIT/NOBYPASSRLS role; only claim/complete/retry function grants; no direct table writes; no inbound MAS adapter. | Migration security tests. |
| Data leak through logs | IDs and control outcomes only; no document body, TOTP secret, magic token, recovery code, or signed URL logged by application code. | Logging review before deployment. |
| Backup exfiltration | Encrypted database/storage backups, separate backup role, restore isolation, access logging, documented destruction. | Backup runbook. |

## Residual risks requiring deployment decisions

WAF/rate-limit tuning, identity-provider email delivery security, host hardening, key management/HSM posture, regional residency, bucket versioning/object lock, retention/legal hold, malware definition freshness, PDF parser sandboxing, dependency scanning, observability sink, and independent penetration testing are environment responsibilities rather than facts asserted by this source archive.
