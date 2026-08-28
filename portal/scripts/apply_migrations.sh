#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 1 ]]; then echo "usage: $0 DATABASE_ADMIN_URL" >&2; exit 2; fi
command -v psql >/dev/null || { echo "psql is required" >&2; exit 1; }
root="$(cd "$(dirname "$0")/.." && pwd)"
for migration in "$root"/migrations/[0-9][0-9][0-9][0-9]_*.sql; do
  echo "applying $(basename "$migration")"
  psql "$1" --set=ON_ERROR_STOP=1 --file="$migration"
done
