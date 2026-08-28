# API surface

All routes are under `/api/v1`. Authentication uses the `gg_session` secure HttpOnly cookie. Mutations require exact allowed Origin plus `gg_csrf` cookie / `X-CSRF-Token` header equality. Responses use no-store headers.

## Authentication

- `POST /auth/magic-link` — generic accepted response.
- `POST /auth/magic-link/consume` — consume one-time link and set session.
- `POST /auth/invitation/consume` — activate an invitation through the server RPC and set session.
- `POST /auth/totp/enroll`, `/confirm`, `/step-up` — context-encrypted TOTP lifecycle.
- `POST /auth/recovery` — consume one recovery code.
- `POST /auth/logout` — revoke session and clear cookie.
- `GET /me` — current server-derived role/scope and step-up status.

## Documents

- `GET /document-requests` — in-scope checklist and document states.
- `POST /advisor/document-requests` — advisor/operations request.
- `POST /uploads` — idempotent upload/document allocation and generated quarantine key.
- `POST /uploads/{id}/parts/{n}/capability` — bounded short-lived part authority.
- `PUT /uploads/{id}/parts/{n}` — upload part under capability.
- `GET /uploads/{id}` — authorized resume/progress state.
- `POST /uploads/{id}/complete` — ordered completion and authoritative metadata.
- `POST /support` — the single client support action.
- `POST /advisor/documents/{id}/review` — accept/replace/reject.
- `GET /advisor/documents/{id}/download` — short-lived clean-object read authority after step-up.
- `POST /advisor/documents/{id}/delete` — revision-aware deletion job and receipt.

## Advisor access

- `POST /advisor/invitations` — invite role/entity scope after step-up.
- `POST /advisor/revocations` — revoke membership and every active session/link/invitation after step-up.

## Treasury

- `POST /treasury/policies` — initial or base-linked future policy version.
- `POST /treasury/policies/{id}/approve` — designated signer approval with expected revision and step-up.
- `POST /treasury/cash-operations` — policy-bounded, non-executable request.
- `POST /treasury/cash-operations/{id}/approve` — approval for outbound intake only.
- `GET /treasury` — in-scope policy/cash workflows.

See `apps/api/portal_api/schemas.py` for exact payload constraints and `migrations/0006...0009` for authoritative database behavior.
