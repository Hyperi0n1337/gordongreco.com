"""One-off: Replace GitHub Pages temp domain with production domain across all HTML + sitemap."""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
OLD = "https://hyperi0n1337.github.io/gordongreco.com"
NEW = "https://gordongreco.com"

html_files = list(ROOT.glob("**/*.html")) + list(ROOT.glob("sitemap.xml"))

total = 0
for f in html_files:
    text = f.read_text(encoding="utf-8")
    new_text = text.replace(OLD, NEW)
    if new_text != text:
        count = text.count(OLD)
        f.write_text(new_text, encoding="utf-8")
        print(f"  {f.relative_to(ROOT)}: {count} replacements")
        total += count

print(f"\nDone. {total} total replacements across {len(html_files)} files checked.")
