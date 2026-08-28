# Netlify switchover — gordongreco.com

This repository can deploy the public Gordon Greco site directly from `mas/web/` without publishing source scripts, tests, reports, or internal working documents.

## Verified build contract

`netlify.toml` defines:

```toml
[build]
  base = "mas/web"
  command = "bash build.sh"
  publish = "dist"
```

`build.sh` performs three deterministic steps:

1. Generates the 12 committed HTML routes from `scripts/generate_site.py`.
2. Runs the standard-library static contract.
3. Assembles only public HTML, CSS, JavaScript, metadata, and assets under `dist/`.

The generated `dist/build-manifest.json` records the public file hashes. The `dist/` directory is intentionally ignored by Git and rebuilt by Netlify.

## Dashboard settings

| Field | Value |
|---|---|
| Repository | `Hyperi0n1337/Markos_Analytics_Suite` |
| Base directory | `mas/web` |
| Build command | `bash build.sh` |
| Publish directory | `dist` |

Netlify should read these values from `netlify.toml`; confirm they match before any deployment. No deployment or dashboard change was performed by this implementation.

## Pre-deployment verification

Confirm the external Cal.com route, Formspree endpoint, GA4 property and retention configuration, current registration/status language, fee readiness, governing-law language, DNS, and any future authenticated client route. Keep `client.html` at `data-portal-state="not-enabled"` until server-side authentication and authorization are independently verified.

## Manual fallback

`bash mas/web/deploy.sh` builds the site and syncs only `mas/web/dist/` to the legacy standalone repository. It commits locally but does not push automatically.

## Rollback

Reconnect the prior standalone repository or select a prior Netlify deploy. DNS and custom-domain changes are outside this patch.
