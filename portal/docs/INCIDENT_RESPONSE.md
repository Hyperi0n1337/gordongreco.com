# Incident response runbook

## Severity triggers

**SEV-1:** suspected cross-household access, clean-bucket bypass, disclosed session/TOTP/recovery material, unauthorized deletion, receipt mutation, or treasury workflow marked beyond `approved_for_intake`.

**SEV-2:** scanner outage/backlog, repeated capability failures, abnormal invitation volume, object/database reconciliation mismatch, outbox disclosure, or failed restore drill.

## First actions

1. Preserve evidence. Record UTC start time, detector, affected environment, request IDs, session IDs, user IDs, household IDs, object keys, receipt IDs, deployment revision, and key versions. Never copy document bodies into the incident ticket.
2. Contain. Disable the affected ingress or endpoint; revoke targeted memberships/sessions; rotate HMAC/capability keys when exposure is plausible; suspend outbox dispatch; block clean-bucket reads; preserve quarantine.
3. Bound scope. Query audit events and immutable receipts by household and time. Reconcile database document hashes/sizes with both buckets. Review invitation, magic-link, session, capability, worker, and treasury approval activity.
4. Eradicate. Patch the root control, rebuild from pinned images, rotate secrets through the deployment secret manager, update malware definitions, and invalidate stale capabilities/sessions.
5. Recover. Restore service in stages: authentication, read-only metadata, uploads to quarantine, scanner, clean downloads, then outbound queues. Do not skip reconciliation.
6. Close. Produce a timestamped incident report, affected-record decision, owner notifications, control-test evidence, and follow-up deadlines.

## Scenario playbooks

### Suspected cross-household authorization

Disable the implicated endpoint; revoke the session; capture transaction settings and RPC/audit evidence; test the exact user/household/entity pair in an isolated database; inspect membership history; search for every object and receipt touched by the session; re-run all RLS/RPC tests before restoring writes.

### Scanner unavailable or bypass suspected

Stop scanner claim processing and clean-bucket writes. Keep pending bytes quarantined. Mark scanner readiness unhealthy. Reconcile every document moved during the window against stored findings, authoritative SHA-256, and clean-copy verification receipt. Re-scan from quarantine or a preserved immutable copy after repair.

### Session or factor compromise

Increment the user's auth epoch, revoke sessions/magic links/invitations and unused recovery codes, reset TOTP through the reviewed recovery path, inspect invitations/revocations/downloads/deletes/approvals, and rotate broader keys only when blast radius warrants it.

### Treasury workflow anomaly

Suspend treasury outbox channels, verify governing policy version/effective time/designated signers/revisions, ensure `execution_state` remains `not_executable`, invalidate conflicting pending workflows through an auditable owner-approved process, then replay only idempotent outbound envelopes.

## Evidence locations

Database audit/receipt/outbox tables, object access logs, API/WAF logs, worker logs, deployment events, KMS audit logs, email provider logs, and the outbound envelope directory. Production retention and notification deadlines are owner/legal decisions listed in `BOOKS_AND_RECORDS_DECISIONS.md`.
