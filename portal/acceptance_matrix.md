# MAS-RP-402 acceptance matrix

| ID | Requirement | Evidence | Status |
|---|---|---|---|
| A01 | Actual exact-name ZIP with one top-level root | `Archive build and external verification` | **PASS** |
| A02 | Public marketing site separate from private authenticated portal | `apps/public-site, apps/portal-web, nginx/ingress boundary, tests` | **PASS** |
| A03 | Invitation-only passwordless access, TOTP, expiry, recovery, revocation | `auth core/API, migrations 0002/0006, test_auth.py` | **PASS** |
| A04 | Server-derived household/entity scope and restrictive database/storage authorization | `scope.py, Postgres transaction settings, RLS, IAM/bucket policies, tests` | **PASS** |
| A05 | Client checklist, drag/drop/progress/resume, quarantine/review/missing states, one support action | `portal-web/client.js, document RPCs, upload tests` | **PASS** |
| A06 | Advisor invite/revoke/request/review/download/delete, receipt, outbound-only MAS intake | `advisor UI/API/RPCs, immutable receipts, upload tests` | **PASS** |
| A07 | Generated keys, bounded capabilities, authoritative SHA-256/size, interrupted/duplicate handling | `uploads core/API/S3 adapter/RPCs, capability/upload tests` | **PASS** |
| A08 | Fail-closed libmagic, executable/PDF, ClamAV, qpdf controls | `scanning.py/adapters/worker, scanning tests` | **PASS** |
| A09 | Cash operation vs future-effective treasury policy amendment, signers/conflicts/idempotency/outboxes/recalc, no execution | `treasury core/API/RPCs/UI, treasury tests` | **PASS** |
| A10 | Ordered migrations, FORCE RLS, storage policies/RPCs, deploy templates | `migrations 0001-0009, deploy/, migration tests` | **PASS** |
| A11 | Fictional .test fixtures and real authorization/upload/security tests | `fixtures/, 41-test pytest suite` | **PASS** |
| A12 | Threat model, incident response, backup/recovery, books-and-records decisions | `docs/` | **PASS** |
| A13 | Repository-relative changes.patch and implementation manifest | `changes.patch, implementation_manifest.json` | **PASS** |
| A14 | VERIFY.md, acceptance matrix, exact command logs | `VERIFY.md, acceptance_matrix.*, verification/logs/` | **PASS** |
| A15 | No deployment, credentials, real client data, messages, trades, or money movement | `source boundary, fixture checks, outbox-only worker, tests` | **PASS** |
