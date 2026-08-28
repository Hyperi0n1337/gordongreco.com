# Performance implementation notes

## Changes

- Replaced remote Google Fonts with resilient system serif/sans stacks.
- Replaced Tailwind plus the 35KB custom stylesheet with one purpose-built stylesheet.
- Removed the canvas hero runtime and used a lightweight inline SVG whose line motion runs once.
- Replaced the embedded scheduling UI with an explicit external link.
- Cropped and compressed the supplied 386KB square source logo into exact-size WebP navigation marks while retaining the source asset.
- Added explicit image dimensions and deferred local JavaScript.
- Kept interaction logic small and page-specific; the services selector script loads only on `services.html`.
- Added one-week browser caching with stale-while-revalidate for unversioned assets, plus immediate revalidation for HTML in `netlify.toml`.
- Preserved the supplied GA4 snippet unchanged because analytics changes are outside authority.

## Measurement boundary

Local Lighthouse runs use Chromium, a local static HTTP server, mobile throttling defaults, and the same command for baseline and implementation. External GA/Cal/Formspree account availability is not treated as verified. Raw JSON/HTML and a summarized comparison belong under `reports/lighthouse/`.
## Measured three-run median

- Performance: 88 → 100.
- Accessibility: 90 → 100.
- LCP: 3.76 s → 1.61 s (-57.0%).
- FCP / Speed Index: 1.66 s → 0.91 s (-45.0%).
- Transferred bytes: 470 KiB → 48 KiB (-89.8%).
- CLS remained 0; median TBT changed from 0 ms to 11 ms and retained a 100 metric score.

See `reports/PERFORMANCE_COMPARISON.md` and all six raw reports under `reports/lighthouse/*-runs/`.

## Public build isolation

`build.sh` copies only runtime HTML, CSS, JavaScript, metadata, and assets into a public-only `dist/` directory. Source scripts, tests, screenshots, Lighthouse reports, and internal Markdown documents are excluded from the Netlify publish target.
