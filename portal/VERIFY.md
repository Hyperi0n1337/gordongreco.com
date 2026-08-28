# Verification procedure

Run from the repository root with Python 3.12 or newer.

```bash
export PYTHONDONTWRITEBYTECODE=1
python scripts/check_migrations.py
python -m pytest -q
python scripts/verify.py --no-write
node --check apps/portal-web/api.js
node --check apps/portal-web/client.js
node --check apps/portal-web/advisor.js
```

`python scripts/verify.py --no-write` verifies the manifest, required repository layout, Python syntax without writing bytecode, migration ordering and restrictive security controls, JavaScript syntax when Node is installed, all tests, fixture hygiene, public/private separation, no nested archive, no symlinks, and absence of common secret artifacts.

## Database integration gate

The archive build environment did not expose a PostgreSQL server or `psql`; the recorded delivery tests therefore validate SQL structure and domain behavior but do not claim a live PostgreSQL integration run. Before production rollout, create a disposable PostgreSQL 16+ database, apply migrations in filename order, make `portal_api` and `portal_worker` LOGIN roles through the deployment secret mechanism, and run:

```bash
scripts/apply_migrations.sh "$DATABASE_ADMIN_URL"
PORTAL_DATABASE_URL="$PORTAL_DATABASE_URL" python -m pytest -q -m postgres
```

No `postgres`-marked tests are silently skipped in this archive: the available suite is dependency-light and runs in full. A production pipeline should add ephemeral-database contract tests for every RPC and RLS policy.

## Scanner integration gate

Production worker images must provide all three scanner dependencies and pass their readiness probes:

```bash
file --version
clamdscan --version
qpdf --version
```

A missing, timed-out, malformed, or non-clean scanner result is fail-closed. Scanner outage leaves bytes in the quarantine bucket and does not create a clean object.

## Object-storage gate

Verify private bucket posture, API/worker role policies, lifecycle rules, versioning/object lock decision, and signed-capability TTLs against the target account. Browser access must be limited to exact pre-authorized object, method, upload part, size, and expiry. Object keys are server generated; original filenames are display metadata only.

## Archive verification

The delivery process creates one ZIP with one top-level directory, runs Python `ZipFile.testzip()`, external `unzip -t`, duplicate/path/symlink checks, then extracts it into a new temporary directory and runs `python scripts/verify.py --no-write` there. The exact delivered byte count and SHA-256 are reported beside the attachment because a ZIP cannot contain its own final hash without changing that hash.
