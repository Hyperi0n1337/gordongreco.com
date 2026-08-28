#!/bin/bash
# Compatibility deploy: build the public site, then sync dist/ to the standalone
# gordongreco.com repository. Netlify connected to this repo is preferred.
#
# Usage: bash mas/web/deploy.sh [--message "deploy message"]

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WEB_SRC="$REPO_ROOT/mas/web"
PUBLIC_SRC="$WEB_SRC/dist"
WEB_DEST="$(dirname "$REPO_ROOT")/gordongreco.com"
MSG="${1:-deploy: sync from mas/web/dist ($(date +%Y-%m-%d-%H%M))}"

if [ ! -d "$WEB_DEST" ]; then
    echo "ERROR: $WEB_DEST not found. Clone the standalone repo first." >&2
    exit 1
fi

echo "==> 1. Generate, validate, and assemble public dist"
bash "$WEB_SRC/build.sh"

echo "==> 2. Sync public files to $WEB_DEST"
rsync -av --delete --exclude='.git' "$PUBLIC_SRC/" "$WEB_DEST/"

echo "==> 3. Commit in $WEB_DEST"
cd "$WEB_DEST"
git add -A
if git diff --cached --quiet; then
    echo "No changes to deploy."
    exit 0
fi
git commit -m "$MSG"
echo "Committed. Review, then push from $WEB_DEST."
