# Gordon Greco Secure Client Portal — MAS-RP-402

Production-oriented reference implementation for an invitation-only, passwordless client portal that remains operationally and technically separate from the public Gordon Greco marketing site.

## Repository map

| Path | Owner / purpose |
|---|---|
| `apps/public-site/` | Exact public static-site snapshot hydrated from the owner context; no private portal code or data. |
| `apps/portal-web/` | Private client/advisor browser application served only behind the portal origin. |
| `apps/api/portal_api/` | FastAPI edge/API layer, secure cookies, CSRF/origin enforcement, PostgreSQL RPC calls, signed object capabilities. |
| `apps/worker/portal_worker/` | Scanner, object-deletion, outbox, and recalculation worker. It writes outbound MAS envelopes only. |
| `packages/portal_core/` | Dependency-light authorization, authentication, upload, scanning, receipt, and treasury domain model. |
| `packages/portal_adapters/` | PostgreSQL, S3-compatible private storage, KMS/local vault, libmagic, ClamAV, and qpdf adapters. |
| `migrations/` | Ordered PostgreSQL schema, restrictive RLS, RPCs, worker controls, immutability, and grants. |
| `deploy/` | Digest-pinned Docker template, nginx, Kubernetes, and AWS/Terraform policy templates. |
| `fixtures/` | Fictional `.test` fixtures only. |
| `tests/` | Executable authorization, authentication, upload, scanning, treasury, migration, UI, and fixture tests. |
| `docs/` | Architecture, threat model, runbooks, backup/recovery, records decisions, and context proof. |

## Security boundary

The public site contains only a `noindex` orientation shell. The private portal uses a separate origin/path and API, `HttpOnly; Secure; SameSite=Strict` session cookies, synchronizer CSRF cookie/header checks, explicit allowed origins, no permissive CORS, no browser-persisted session bearer token, and no service worker cache.

Household and entity scope are calculated by the server from the authenticated session and active memberships. PostgreSQL receives the derived values as transaction-local settings; every table enables and forces RLS. Mutations occur through fixed-search-path `SECURITY DEFINER` RPCs with role, scope, step-up, revision, and idempotency checks.

## Deliberate non-capabilities

This repository never sends a trade, instruction, payment, transfer, or money movement. Treasury results are `approved_for_intake`, emitted to an outbound-only MAS directory and Telegram outbox, and paired with recalculation jobs. Delivery adapters that contact real clients, Telegram, MAS, custodians, or banks are intentionally absent.

## Local verification

```bash
python scripts/verify.py --no-write
```

See `VERIFY.md` for production-only checks and migration/deployment procedure. Do not use fictional fixtures outside isolated test environments.

## Loopback acceptance demo

MAS includes a fictional test-only browser runtime so the client workflow can
be reviewed before PostgreSQL, private object storage, KMS, and scanners are
provisioned:

```bash
PYTHONDONTWRITEBYTECODE=1 venv/bin/python -m mas.client_portal.apps.demo.server
```

Open `http://127.0.0.1:8520/portal/?invite=ann-demo-invite`. The invitation is
single-use per server run and registers only
`ann.terzidis@example.test`. Uploaded bytes remain in process memory and are
discarded when the demo stops. Never upload real documents to this demo.
