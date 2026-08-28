#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
python scripts/generate_site.py
python tests/run_static_contract.py
python scripts/build_public.py
printf 'Gordon Greco static site generated, validated, and assembled in dist/.\n'
