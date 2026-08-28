#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
python scripts/generate_site.py --check
python tests/run_static_contract.py
python scripts/build_public.py
python -m http.server "${GG_PORT:-8000}" --bind 127.0.0.1 --directory dist >/tmp/gordon-greco-http.log 2>&1 &
server_pid=$!
trap 'kill "$server_pid" 2>/dev/null || true' EXIT
for _ in $(seq 1 50); do curl -fsS "http://127.0.0.1:${GG_PORT:-8000}/index.html" >/dev/null && break || sleep .1; done
python tests/browser_audit.py \
  --base-url "http://127.0.0.1:${GG_PORT:-8000}/" \
  --output reports/browser \
  --viewport "${GG_VIEWPORT:-all}" \
  --screenshots
