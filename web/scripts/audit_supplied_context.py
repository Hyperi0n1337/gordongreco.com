#!/usr/bin/env python3
"""Create a deterministic read-proof inventory for the supplied Gordon Greco context."""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
from pathlib import Path

TEXT_SUFFIXES = {
    '.py', '.html', '.css', '.js', '.md', '.txt', '.xml', '.toml', '.json',
    '.sh', '.gitignore',
}
IMAGE_SUFFIXES = {'.png', '.ico', '.jpg', '.jpeg', '.webp'}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def image_metadata(path: Path) -> dict:
    try:
        from PIL import Image
        with Image.open(path) as image:
            return {
                'format': image.format,
                'width': image.width,
                'height': image.height,
                'mode': image.mode,
                'read_method': 'Pillow decode',
            }
    except Exception as exc:
        return {'read_method': 'binary read', 'decode_note': str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    rows = []
    for path in sorted(item for item in root.rglob('*') if item.is_file() and '.git' not in item.parts):
        raw = path.read_bytes()
        relative = path.relative_to(root).as_posix()
        row = {
            'path': relative,
            'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest(),
            'mime': mimetypes.guess_type(path.name)[0] or 'application/octet-stream',
        }
        suffix = path.suffix.lower()
        if suffix in IMAGE_SUFFIXES:
            row.update(image_metadata(path))
        else:
            text = raw.decode('utf-8')
            row.update({
                'utf8_read': True,
                'line_count': text.count('\n') + (1 if text or not raw else 0),
                'character_count': len(text),
                'read_method': 'UTF-8 full-file decode',
            })
        rows.append(row)

    result = {
        'source_root': str(root),
        'archive': None,
        'file_count': len(rows),
        'total_bytes': sum(row['bytes'] for row in rows),
        'all_files_read': all(row.get('utf8_read') or row.get('read_method') in {'Pillow decode', 'binary read'} for row in rows),
        'files': rows,
    }
    if args.archive:
        result['archive'] = {
            'path': str(args.archive.resolve()),
            'bytes': args.archive.stat().st_size,
            'sha256': sha256(args.archive),
        }

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'provider_read_proof.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    lines = [
        '# Supplied context read proof', '',
        f"- Files fully read: **{result['file_count']}**",
        f"- Total uncompressed bytes: **{result['total_bytes']:,}**",
        f"- All files read successfully: **{str(result['all_files_read']).lower()}**",
    ]
    if result['archive']:
        lines += [f"- Archive SHA-256: `{result['archive']['sha256']}`"]
    lines += ['', '| Path | Bytes | Read proof | SHA-256 |', '|---|---:|---|---|']
    for row in rows:
        proof = row['read_method']
        if 'width' in row:
            proof += f"; {row['width']}×{row['height']} {row.get('format', '')}"
        elif 'line_count' in row:
            proof += f"; {row['line_count']} lines"
        lines.append(f"| `{row['path']}` | {row['bytes']:,} | {proof} | `{row['sha256']}` |")
    (args.output / 'provider_read_proof.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({k: result[k] for k in ['file_count', 'total_bytes', 'all_files_read']}, indent=2))


if __name__ == '__main__':
    main()
