"""Headless render-check of privacy.html + terms.html."""
from playwright.sync_api import sync_playwright
from pathlib import Path

OUT = Path(r"C:\github\gordongreco.com\scripts\_screens")
OUT.mkdir(exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(f"JS error: {e}"))
    page.on("console", lambda m: errors.append(f"console {m.type}: {m.text}") if m.type in ("error",) else None)

    for name in ("privacy", "terms", "index", "about"):
        url = f"http://127.0.0.1:8765/{name}.html"
        page.goto(url, wait_until="networkidle", timeout=15000)
        # Verify heading
        h1 = page.locator("h1").first.inner_text()
        # Verify footer links both visible
        has_priv = page.locator("footer a[href='privacy.html']").count() > 0
        has_terms = page.locator("footer a[href='terms.html']").count() > 0
        page.screenshot(path=str(OUT / f"{name}_top.png"), full_page=False)
        page.screenshot(path=str(OUT / f"{name}_full.png"), full_page=True)
        print(f"[{name}] h1={h1!r}  footer(priv={has_priv}, terms={has_terms})")

    if errors:
        print("\nERRORS:")
        for e in errors:
            print("  " + e)
    else:
        print("\n[clean] no JS/console errors")

    browser.close()
print("Screenshots in", OUT)
