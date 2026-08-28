# Free Cloudflare portal deployment

This adapter runs the Gordon Greco onboarding portal on the Cloudflare Workers
Free plan. D1 holds strongly consistent identity, session, request, document
metadata, and audit rows. Workers KV holds generated-key quarantine objects up
to 20 MiB. The public GitHub Pages site never receives private state.

The client portal does not preview uploaded bytes. Every upload remains
`quarantined` until Markos downloads it as an attachment, scans it locally, and
records an `accepted` or `replace` decision. No trade, transfer, payment, or
broker instruction exists in this adapter.

Deployment requires two Wrangler secrets, neither committed:

```bash
npx wrangler secret put ADMIN_API_KEY --config deploy/cloudflare/wrangler.jsonc
npx wrangler secret put SESSION_PEPPER --config deploy/cloudflare/wrangler.jsonc
npx wrangler d1 execute gg-portal --remote --file deploy/cloudflare/schema.sql
npx wrangler deploy --config deploy/cloudflare/wrangler.jsonc
```

The local MAS onboarding controller calls the admin invitation endpoint, then
sends the returned single-use URL through the existing Gordon Greco Gmail
sender. The admin bearer never enters browser JavaScript.
