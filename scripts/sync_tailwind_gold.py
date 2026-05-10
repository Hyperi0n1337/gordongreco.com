"""Patch the precompiled tailwind.min.css to use the PDF-aligned gold gradient stops."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "css" / "tailwind.min.css"
src = p.read_text(encoding="utf-8")
orig = src

# Gradient mid-stop: #d4b88a → #d3b791 (halfway between #c8a97e and #dfc5a4)
src = src.replace("#d4b88a", "#d3b791")

# RGB muted: 212, 175, 55 → 200, 169, 126
src = src.replace("rgba(212,175,55,", "rgba(200,169,126,")
src = src.replace("rgba(212, 175, 55,", "rgba(200, 169, 126,")

# Direct hex accents in case any slipped in
src = src.replace("#d4af37", "#c8a97e")
src = src.replace("#e6c875", "#dfc5a4")

if src != orig:
    p.write_text(src, encoding="utf-8")
    print("[ok] patched tailwind.min.css")
else:
    print("[skip] no changes")
