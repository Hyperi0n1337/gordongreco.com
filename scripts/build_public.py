#!/usr/bin/env python3
"""Assemble the public static site without source, tests, reports, or internal docs."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
ROOT_FILES = (
    ".nojekyll",
    "llms-full.txt",
    "llms.txt",
    "robots.txt",
    "sitemap.xml",
)
PUBLIC_DIRS = {
    "assets": None,  # copy supplied public assets as-is
    "css": {"site.css"},
    "js": {"decision-view.js", "site.js"},
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def main() -> int:
    shutil.rmtree(DIST, ignore_errors=True)
    DIST.mkdir(parents=True)

    pages = sorted(ROOT.glob("*.html")) + sorted((ROOT / "services").glob("*.html"))
    if len(pages) != 12:
        raise SystemExit(f"Expected 12 generated HTML pages, found {len(pages)}")
    for page in pages:
        copy_file(page, DIST / page.relative_to(ROOT))

    for name in ROOT_FILES:
        copy_file(ROOT / name, DIST / name)

    for directory, allowlist in PUBLIC_DIRS.items():
        source_dir = ROOT / directory
        for source in sorted(path for path in source_dir.iterdir() if path.is_file()):
            if allowlist is None or source.name in allowlist:
                copy_file(source, DIST / directory / source.name)

    forbidden = [
        path.relative_to(DIST).as_posix()
        for path in DIST.rglob("*")
        if path.is_file() and (path.suffix in {".py", ".md"} or "reports" in path.parts or "tests" in path.parts)
    ]
    if forbidden:
        raise SystemExit(f"Non-public files entered dist: {forbidden}")

    files = sorted(path for path in DIST.rglob("*") if path.is_file())
    manifest = {
        "payload_file_count": len(files),
        "payload_bytes": sum(path.stat().st_size for path in files),
        "manifest_excluded_from_counts": True,
        "files": [
            {
                "path": path.relative_to(DIST).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in files
        ],
    }
    (DIST / "build-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Public dist assembled: {manifest['payload_file_count']} payload files, {manifest['payload_bytes']} bytes, plus build-manifest.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
