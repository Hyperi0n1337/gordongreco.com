# Architecture and trust boundaries

```text
Public Internet
  |
  +--> public-site origin ---------------- static files only; no auth/data API
  |
  +--> portal origin
         | HTTPS / strict origin / CSRF / secure cookies
         v
      nginx / WAF
         |
         +--> portal-web (private UI)
         +--> portal-api (portal_api DB role)
                | transaction-local server-derived scope
                +--> PostgreSQL 16+ (FORCE RLS + RPC-only writes)
                +--> private object service (short-lived capabilities)

      portal-worker (portal_worker DB role)
         +--> quarantine bucket --> libmagic --> executable/PDF controls
                                 --> ClamAV --> qpdf
                                 --> clean bucket only after every control passes
         +--> deletion queue
         +--> outbound-only MAS / Telegram / email envelope directories
         +--> recalculation queue
```

## Components

The API authenticates opaque, HMAC-digested session tokens. It never accepts household, entity, or role claims from a browser as authorization facts. It calls `portal.authenticate_session`, sets `app.user_id`, `app.session_id`, `app.actor_role`, `app.household_ids`, `app.entity_ids`, and the household/entity pair list with `SET LOCAL`, then uses read-only RLS queries or narrow RPCs.

The worker has no client session. Each worker transaction sets an asserted worker identity and may execute only explicitly granted claim/complete/retry RPCs. Work claims use `FOR UPDATE SKIP LOCKED`; retries are bounded and visible.

The two storage buckets are private. Uploads land only in quarantine under generated keys. The authoritative size and SHA-256 are calculated from stored bytes. Clean storage is populated by server-side copy only after all scanner controls pass and the copied bytes are rechecked.

## Authentication lifecycle

1. A step-up-authenticated advisor creates an invitation for a household role and entity set.
2. Outbound delivery is queued; no sender is embedded in the portal API.
3. An invited or active user requests a generic-response magic link.
4. Consumption is one-time and expiring. First use consumes the active invitation.
5. The browser receives an opaque session in a secure cookie.
6. TOTP step-up is mandatory for invitations, revocations, downloads, deletions, and treasury approvals.
7. Recovery codes are HMAC-digested, shown once, and consumed once.
8. Revocation increments `auth_epoch`, revokes active sessions/links/invitations, and removes the membership.

## Data ownership

PostgreSQL is authoritative for identity, scope, workflow state, object metadata, hashes, receipts, idempotency, and outboxes. Object storage is authoritative only for bytes. MAS receives outbound intake envelopes and is not allowed to call back to mutate portal workflow state in this implementation.
