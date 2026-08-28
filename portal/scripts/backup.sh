#!/usr/bin/env bash
set -euo pipefail
: "${DATABASE_ADMIN_URL:?set DATABASE_ADMIN_URL}"
: "${BACKUP_DIR:?set BACKUP_DIR to an encrypted, access-controlled destination}"
command -v pg_dump >/dev/null || { echo "pg_dump is required" >&2; exit 1; }
mkdir -p "$BACKUP_DIR"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
out="$BACKUP_DIR/portal-$stamp.dump"
pg_dump "$DATABASE_ADMIN_URL" --format=custom --no-owner --no-privileges --file="$out"
sha256sum "$out" > "$out.sha256"
echo "database backup created; object-store backup/versioning must be verified separately: $out"
