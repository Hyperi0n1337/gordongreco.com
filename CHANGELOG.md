# mas.web Changelog

## 2026-05-10

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
