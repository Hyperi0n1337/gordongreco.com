# Security control specification

## Authentication

- Invitation required for first activation; only a step-up-authenticated household advisor can invite or revoke.
- Passwordless magic links are random, one-time, expiring, HMAC-digested, and replaced when reissued.
- Sessions are opaque, HMAC-digested, expiring, revocable, and bound to the user's current `auth_epoch`.
- TOTP secrets are encrypted with a user/purpose context; replayed counters are rejected.
- Recovery codes are random, HMAC-digested, shown once, consumed once, and rotated on enrollment.

## Authorization

- API ignores browser-supplied role/scope claims.
- Household, entity, role, and step-up facts are transaction-local server settings.
- Entity authority is a `(household_id, entity_id)` pair, not a global entity-ID set.
- Every table uses `ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY`.
- API/worker roles have no direct INSERT/UPDATE/DELETE table grants.
- Privileged RPCs are `SECURITY DEFINER`, pin `search_path = pg_catalog, portal`, revoke public execute, and validate target scope.

## Upload/storage

- Original filenames never become storage keys.
- Quarantine and clean buckets are private and have separate role policies.
- Capabilities are short-lived and bind actor, household, resource, bucket, key, method, part, byte limit, issued-at, expiry, and unique ID.
- Browser progress is multipart; resume reuses only server-reported parts with matching part number, size, and ETag.
- Completion calculates authoritative size and SHA-256 from stored bytes.
- Duplicate content within a household is explicitly linked and redundant bytes are deleted.
- Missing scanner dependency or ambiguous result is not clean.

## Browser/API

- TLS-only deployment, HSTS at ingress, restrictive CSP, frame denial, no sniffing, referrer restrictions, and no cache for portal pages/API.
- Session is cookie-only and inaccessible to JavaScript.
- Non-secret upload IDs may live in session storage solely to recover an interrupted multipart transfer; every resume is reauthorized by the server.
- No service worker, no offline document cache, no public object URL, and no raw client document in application logs.

## Workflow integrity

- Idempotency keys cover invite-sensitive workflows, upload creation, policy versions, and cash operations.
- Expected revisions prevent lost updates.
- Immutable receipt and approval triggers deny update/delete.
- Treasury policy amendments are future-effective and conflict with stale/pending base versions.
- Cash operations inherit designated signers/threshold from an approved policy and require at least one advisor approval.
- Side effects are transactional outbox and recalculation rows; they do not execute financial activity.
