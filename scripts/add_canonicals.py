"""One-off: Add canonical link tags to all HTML pages that are missing them."""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Map each HTML file to its canonical URL
page_map = {
    "index.html":               "https://gordongreco.com/",
    "about.html":               "https://gordongreco.com/about.html",
    "services.html":            "https://gordongreco.com/services.html",
    "contact.html":             "https://gordongreco.com/contact.html",
    "services/investment.html": "https://gordongreco.com/services/investment.html",
    "services/tax.html":        "https://gordongreco.com/services/tax.html",
    "services/retirement.html": "https://gordongreco.com/services/retirement.html",
    "services/estate.html":     "https://gordongreco.com/services/estate.html",
    "services/business.html":   "https://gordongreco.com/services/business.html",
}

for rel_path, canonical_url in page_map.items():
    f = ROOT / rel_path
    if not f.exists():
        print(f"MISSING: {rel_path}")
        continue
    text = f.read_text(encoding="utf-8")
    if 'rel="canonical"' in text:
        print(f"SKIP (already has canonical): {rel_path}")
        continue
    canonical_tag = f'  <link rel="canonical" href="{canonical_url}">\n'
    # Insert after the apple-touch-icon line
    new_text = re.sub(
        r'(  <link rel="apple-touch-icon"[^\n]+\n)',
        r'\1' + canonical_tag,
        text,
        count=1,
    )
    if new_text == text:
        # Fallback: insert before closing </head>
        new_text = text.replace("</head>", canonical_tag + "</head>", 1)
    f.write_text(new_text, encoding="utf-8")
    print(f"  Added canonical to {rel_path}: {canonical_url}")

print("\nDone.")
