# Gordon Greco Client Portal Boundary

`mas/web/` remains a public, static marketing surface. `client.html` is a
noindex orientation shell, not a portal. It must not gain credentials, account
data, document uploads, calculations, or client-specific state through static
JavaScript.

The authenticated portal, when approved, needs its own trust boundary:

```text
public brand and client shell -> authenticated portal -> scoped product API -> MAS adapters
```

- Authentication and client/household authorization are enforced server-side;
  the browser never supplies its own scope.
- The portal consumes versioned, client-safe read models and signed document
  metadata. It does not embed Streamlit or query MAS operational tables or
  broker integrations directly.
- A source-derived value carries source, as-of time, freshness, scope, and an
  explicit unavailable state. Missing values never become zero.
- Initial pilot actions are read-only report delivery and reviewable requests.
  Uploads, messages, scenario calculations, and any execution-adjacent action
  require their own auditable authorization and recovery paths.
- Ordinary cash-operation requests under an effective treasury policy and
  proposed treasury-policy amendments are different workflows. An amendment
  remains pending while the portal shows its liquidity/risk/solver deltas,
  notifies the advisor through the existing Telegram owner, and awaits an
  explicit approve/reject/request-clarification decision. Approval versions
  policy and recalculates affected advice; it never submits a trade or money
  movement by itself.

The visible client shell intentionally states `data-portal-state="not-enabled"`.
Change that state only when an authenticated route, server-side tenant controls,
and a bounded pilot workflow have been built and verified.
