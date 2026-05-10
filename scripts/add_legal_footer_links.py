"""Add Privacy/Terms links in the footer-disclosure block of every HTML page
that doesn't already have them. Idempotent.
"""
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]

ROOT_BLOCK_FROM = (
    '        <p class="text-xs text-gray-600">\n'
    '          &copy; <span id="copyright-year"></span> Gordon Greco LLC. All rights reserved.\n'
    '        </p>'
)
ROOT_BLOCK_TO = (
    '        <p class="text-xs text-gray-600 mb-2">\n'
    '          <a href="privacy.html" class="hover:text-white transition">Privacy Policy</a>\n'
    '          <span class="mx-2">&middot;</span>\n'
    '          <a href="terms.html" class="hover:text-white transition">Terms &amp; Disclosures</a>\n'
    '        </p>\n'
    '        <p class="text-xs text-gray-600">\n'
    '          &copy; <span id="copyright-year"></span> Gordon Greco LLC. All rights reserved.\n'
    '        </p>'
)

# Service sub-pages use ../ prefix
SUB_BLOCK_FROM = ROOT_BLOCK_FROM
SUB_BLOCK_TO = ROOT_BLOCK_TO.replace('"privacy.html"', '"../privacy.html"') \
                             .replace('"terms.html"',   '"../terms.html"')

root_pages = ["index.html", "about.html", "services.html", "contact.html"]
sub_pages  = ["services/investment.html", "services/tax.html",
              "services/retirement.html", "services/estate.html",
              "services/business.html"]

def patch(path: Path, old: str, new: str, already_marker: str = '>Privacy Policy<'):
    txt = path.read_text(encoding="utf-8")
    if already_marker in txt:
        print(f"[skip] {path.name} already has Privacy link")
        return False
    if old not in txt:
        print(f"[WARN] {path.name} — footer block not found")
        return False
    new_txt = txt.replace(old, new, 1)
    path.write_text(new_txt, encoding="utf-8")
    print(f"[ok]   {path.relative_to(SITE)}")
    return True

changed = 0
for p in root_pages:
    if patch(SITE / p, ROOT_BLOCK_FROM, ROOT_BLOCK_TO):
        changed += 1
for p in sub_pages:
    if patch(SITE / p, SUB_BLOCK_FROM, SUB_BLOCK_TO):
        changed += 1

print(f"\n{changed} file(s) updated")
