#!/usr/bin/env bash
set -euo pipefail

: "${POSTGRES_USER:?required}"
: "${POSTGRES_DB:?required}"
: "${PORTAL_API_DB_PASSWORD:?required}"
: "${PORTAL_WORKER_DB_PASSWORD:?required}"

for migration in /migrations/[0-9][0-9][0-9][0-9]_*.sql; do
  printf 'Applying %s\n' "${migration##*/}"
  psql --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --file "$migration"
done

psql \
  --set=ON_ERROR_STOP=1 \
  --set=api_password="$PORTAL_API_DB_PASSWORD" \
  --set=worker_password="$PORTAL_WORKER_DB_PASSWORD" \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" <<'SQL'
ALTER ROLE portal_api LOGIN PASSWORD :'api_password';
ALTER ROLE portal_worker LOGIN PASSWORD :'worker_password';
ALTER ROLE portal_api SET statement_timeout = '30s';
ALTER ROLE portal_api SET idle_in_transaction_session_timeout = '30s';
ALTER ROLE portal_worker SET statement_timeout = '5min';
ALTER ROLE portal_worker SET idle_in_transaction_session_timeout = '30s';
SQL
