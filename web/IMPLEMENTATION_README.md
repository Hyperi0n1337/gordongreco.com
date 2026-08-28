# Gordon Greco website implementation

## What changed

The existing static Gordon Greco site was redesigned in place. It remains a static HTML/CSS/JS site, retains the supplied brand assets and deployment shape, preserves the existing analytics ID and public contact/scheduling routes, and does not create authentication, uploads, account data, or client-specific state.

Canonical page source is `scripts/generate_site.py`; generated HTML is committed so the site can deploy without a Python runtime.

## Build

From repository root:

```bash
cd mas/web
bash build.sh
```

`build.sh` regenerates all 12 HTML pages, runs the 8-test standard-library contract, and assembles a public-only `dist/` directory. Netlify publishes `dist/`, so source scripts, tests, reports, and internal documents are not deployed; deployment does not depend on pytest.

## Local preview

```bash
cd mas/web
bash build.sh
python -m http.server 8000 --bind 127.0.0.1 --directory dist
# open http://127.0.0.1:8000/index.html
```

## Static and browser verification

Requirements: Python 3.11+, Playwright for Python, and Chromium/Chrome.

```bash
python -m pip install playwright
python -m playwright install chromium
cd mas/web
GG_CHROME_PATH=/path/to/chromium bash scripts/run_verification.sh
```

The runner checks all 12 routes at mobile, tablet, and desktop sizes, writes 36 screenshots, and verifies overflow, images, JavaScript errors, reduced motion, no-JavaScript fallback, mobile navigation focus, and keyboard tabs.

Split viewport runs are supported:

```bash
GG_VIEWPORT=mobile  GG_PORT=8001 GG_CHROME_PATH=/path/to/chromium bash scripts/run_verification.sh
GG_VIEWPORT=tablet  GG_PORT=8002 GG_CHROME_PATH=/path/to/chromium bash scripts/run_verification.sh
GG_VIEWPORT=desktop GG_PORT=8003 GG_CHROME_PATH=/path/to/chromium bash scripts/run_verification.sh
```

## Lighthouse

Start the local server, then run the Chromium DevTools-bundled Lighthouse client:

```bash
cd mas/web
python -m http.server 8000 --bind 127.0.0.1 --directory dist
# in a second shell, from mas/web:
python tests/lighthouse_devtools_audit.py \
  http://127.0.0.1:8000/index.html \
  --output reports/lighthouse/local-run \
  --chrome /path/to/chromium \
  --port 9465
```

The script maps Google Fonts and Google Tag Manager hosts to localhost so a local audit transmits no analytics. This creates the documented shared console-error deduction. An enterprise-managed browser that blocks local URLs must be replaced with an unmanaged test browser or have that local policy adjusted by its administrator.

The delivered comparison uses a three-run component-wise median. To reproduce the baseline, extract the supplied context archive, serve its `mas/web` directory on a different local port, and run the same command three times against each version.

## Existing Python checks

```bash
# From repository root
python mas/web/tests/run_static_contract.py
python -m pytest -q mas/web/tests/test_site_static.py
python -m pytest -q mas/tests/test_advisory_client_conversion.py
python -m compileall -q mas
bash -n mas/web/build.sh mas/web/deploy.sh mas/web/scripts/run_verification.sh
```

The supplied subset's full test collection also imports `mas.ops.windows_deliverables`, which is absent from the archive. That inherited collection failure is retained in `reports/tests/full_supplied_tests.txt`; unrelated advisory Python was not modified.

## Deployment boundary

No deployment was performed. Before deployment, verify the Cal.com route, Formspree endpoint, GA4 ownership/configuration, retention settings, registration/status language, fee readiness, governing-law language, and any future authenticated portal route. Do not change `data-portal-state="not-enabled"` until the server-side portal boundary is independently verified.
