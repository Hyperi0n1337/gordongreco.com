"""Headless render-check of Gordon Greco static site pages."""
import os
from playwright.sync_api import sync_playwright
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("GG_WEB_SCREENSHOT_OUT", ROOT / "scripts" / "_screens"))
BASE_URL = os.environ.get("GG_WEB_SCREENSHOT_BASE_URL", "http://127.0.0.1:8765").rstrip("/")
OUT.mkdir(parents=True, exist_ok=True)

PAGES = {
    "index": "index.html",
    "about": "about.html",
    "services": "services.html",
    "contact": "contact.html",
    "privacy": "privacy.html",
    "terms": "terms.html",
}

VIEWPORTS = {
    "desktop": {"width": 1280, "height": 900},
    "mobile": {"width": 390, "height": 844},
}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    errors = []

    for viewport_name, viewport in VIEWPORTS.items():
        ctx = browser.new_context(viewport=viewport)
        page = ctx.new_page()
        page.on("pageerror", lambda e: errors.append(f"JS error: {e}"))
        page.on("console", lambda m: errors.append(f"console {m.type}: {m.text}") if m.type in ("error",) else None)

        for name, file_name in PAGES.items():
            url = f"{BASE_URL}/{file_name}"
            response = page.goto(url, wait_until="networkidle", timeout=15000)
            if response is None or response.status >= 400:
                errors.append(f"{viewport_name}/{name}: HTTP {response.status if response else 'no response'}")

            h1 = page.locator("h1").first.inner_text(timeout=5000)
            has_priv = page.locator("footer a[href='privacy.html']").count() > 0
            has_terms = page.locator("footer a[href='terms.html']").count() > 0
            broken_images = page.locator("img").evaluate_all(
                "(imgs) => imgs.filter((img) => !img.complete || img.naturalWidth === 0).map((img) => img.getAttribute('src'))"
            )
            if broken_images:
                errors.append(f"{viewport_name}/{name}: broken images {broken_images}")
            if not has_priv or not has_terms:
                errors.append(f"{viewport_name}/{name}: missing footer legal links")

            page.screenshot(path=str(OUT / f"{name}_{viewport_name}_top.png"), full_page=False)
            page.screenshot(path=str(OUT / f"{name}_{viewport_name}_full.png"), full_page=True)
            print(
                f"[{viewport_name}/{name}] h1={h1!r} "
                f"footer(priv={has_priv}, terms={has_terms}) images={page.locator('img').count()}"
            )

        ctx.close()

    if errors:
        print("\nERRORS:")
        for e in errors:
            print("  " + e)
        raise SystemExit(1)
    else:
        print("\n[clean] no JS/console errors")

    browser.close()
print("Screenshots in", OUT)
