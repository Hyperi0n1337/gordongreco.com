# Netlify Switchover — gordongreco.com

Move Netlify from the standalone `gordongreco.com` repo to deploying `mas/web/`
directly from `Markos_Analytics_Suite`.

---

## Why this is safe

`mas/web/netlify.toml` already exists with:

```toml
[build]
  base    = "mas/web"
  command = "bash build.sh"
  publish = "."
```

Netlify will `cd mas/web`, run `bash build.sh` (Tailwind compile), then serve the result.
The build regenerates brand tokens, compiles Tailwind utilities into
`css/tailwind.min.css`, and leaves the custom site stylesheet `css/style.css`
untouched.

---

## Steps (Netlify dashboard — ~5 minutes)

### 1 — Open Site Settings

Go to: **app.netlify.com** → select the `gordongreco.com` site → **Site configuration**
(left sidebar) → **Build & deploy** → **Continuous deployment**

### 2 — Disconnect the current repo

Under **Repository**, click **Link to a different repository**.  
(If you see "Manage repository access", that just opens GitHub OAuth — allow it.)

### 3 — Pick the new repo

- Git provider: **GitHub**
- Repository: **`Hyperi0n1337/Markos_Analytics_Suite`**

### 4 — Set build settings

| Field | Value |
|---|---|
| Base directory | `mas/web` |
| Build command | `bash build.sh` |
| Publish directory | `.` |

> Netlify reads `netlify.toml` automatically once the repo is linked, so these may
> pre-fill. Verify they match; override if not.

### 5 — Deploy

Click **Save** / **Deploy site**. Netlify triggers a build. Watch the deploy log —
`build.sh` runs Tailwind and exits 0 in ~10 seconds.

---

## After switching

- `deploy.sh` + the `gordongreco.com` standalone repo are fallback-only. Every
  push to `main` in `Markos_Analytics_Suite` that touches `mas/web/**` triggers
  a Netlify build automatically after the site is linked.
- The `gordongreco.com` repo can be archived or left as-is (Netlify won't touch it).
- DNS / custom domain (`gordongreco.com` CNAME) is unchanged — Netlify keeps the same
  domain config.

---

## Rollback

If something goes wrong: go back to **Link to a different repository** and reconnect
`Hyperi0n1337/gordongreco.com`. The standalone repo is still at its last pushed state.
