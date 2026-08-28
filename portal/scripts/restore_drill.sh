#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 2 ]]; then echo "usage: $0 RESTORE_DATABASE_URL BACKUP.dump" >&2; exit 2; fi
command -v pg_restore >/dev/null || { echo "pg_restore is required" >&2; exit 1; }
root="$(cd "$(dirname "$0")/.." && pwd)"
pg_restore --clean --if-exists --no-owner --no-privileges --dbname="$1" "$2"
PYTHONDONTWRITEBYTECODE=1 python "$root/scripts/check_migrations.py"
PYTHONDONTWRITEBYTECODE=1 python "$root/scripts/verify.py" --no-write
echo "database restore completed; object/state/hash/outbox reconciliation remains mandatory per docs/BACKUP_RECOVERY.md"
