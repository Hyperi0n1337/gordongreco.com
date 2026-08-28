# mas.web Changelog

## 2026-08-28

- Rebuilt the public site around one generated source and a public-only `dist/` deployment, reducing copy and runtime weight while adding responsive, accessibility, link, image, and static-boundary tests.
- Replaced the legacy Tailwind/canvas runtime with one local stylesheet, a small deferred site controller, an accessible decision-view control, explicit image dimensions, reduced-motion behavior, and isolated public build output.
- Reframed every route around the current pre-registration planning/research boundary and kept Client Access invitation-only with no fake login, upload, account data, or browser-stored client state.

## 2026-08-02

- Reworked the active home page around one 1% annual AUM advisory fee, billed
  quarterly, and removed the public tier menu and its clipped "Most Popular"
  badge. All site navigation now points to the single Fees section.
- Added a plain-language RIA pilot explanation: MAS supports current household
  information and reviewable analysis alongside an advisor's existing systems;
  it does not claim to replace them. The existing public client-access shell
  remains unchanged.
- Replaced the generic home-page headline with the concrete service statement
  "Up-to-date financial information and professional financial and mathematical
  analysis."
- Added a public, noindex `client.html` invitation shell that uses the shared
  Gordon Greco design language but deliberately exposes no login, account data,
  document upload, calculation, or instruction controls.
- Linked the public home navigation and footer to the new client-access entry
  point, and refreshed the home hero copy to a more measured advisory voice.
- Extended the static visual smoke check to verify the client shell renders at
  desktop and mobile sizes and contains no fake portal controls.

## 2026-07-20

- Changed the policy screenshot helper's default local base URL from port 8765
  to port 8000 so it no longer collides with Agent Mail's local HTTP service;
  `GG_WEB_SCREENSHOT_BASE_URL` still overrides the default.

## 2026-05-10

- Removed the stale `gordongreco.com` GitHub Pages CNAME so the public
  `github.io/gordongreco.com` preview URL can resolve while DNS is unset.
- Aligned the static website runtime CSS/JS with advisory brand tokens: Tailwind
  legacy aliases now read from the generated preset, `style.css` uses generated
  RGB token variables for gold effects, and the hero canvas reads token values
  instead of carrying stale hardcoded brand colors.
- Made the website screenshot script configurable by base URL and output path so
  theme-audit evidence can be captured without colliding with agent-mail on
  port 8765.
- Fixed the website build script so Tailwind compiles to `css/tailwind.min.css`
  instead of overwriting the custom `css/style.css`.
- Made website maintenance scripts resolve paths from `mas/web/` instead of the
  old standalone `C:\github\gordongreco.com` checkout.
- Updated Netlify switchover docs to use publish directory `.` when the Netlify
  base directory is `mas/web`, and clarified that `deploy.sh` is fallback-only.
- Refreshed the website polish prompt to point at the integrated `mas/web/` and
  `mas/advisory/` paths instead of retired standalone/legacy locations.
