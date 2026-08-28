#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
paths = sorted((ROOT / "migrations").glob("[0-9][0-9][0-9][0-9]_*.sql"))
expected = [f"{n:04d}" for n in range(1, 10)]
assert [p.name[:4] for p in paths] == expected, "migration sequence must be 0001..0009"
sql = "\n".join(p.read_text(encoding="utf-8") for p in paths)
for path in paths:
    text = path.read_text(encoding="utf-8").strip()
    assert text.startswith("BEGIN;") and text.endswith("COMMIT;"), f"transaction wrapper: {path.name}"
tables = set(re.findall(r"CREATE TABLE portal\.([a-z0-9_]+)", sql, re.I))
rls = (ROOT / "migrations/0005_restrictive_rls.sql").read_text(encoding="utf-8")
for table in sorted(tables):
    assert f"ALTER TABLE portal.{table} ENABLE ROW LEVEL SECURITY;" in rls, f"RLS missing: {table}"
    assert f"ALTER TABLE portal.{table} FORCE ROW LEVEL SECURITY;" in rls, f"FORCE RLS missing: {table}"
assert "using (true)" not in rls.lower() and "with check (true)" not in rls.lower()
assert "REVOKE ALL ON ALL FUNCTIONS IN SCHEMA portal FROM PUBLIC" in sql
assert not re.findall(r"grant\s+(?:insert|update|delete|all)\b[^;]*\bto\s+(?:portal_api|portal_worker)\b", sql.lower())
blocks = re.split(r"(?=CREATE OR REPLACE FUNCTION portal\.)", sql, flags=re.I)[1:]
for block in (b for b in blocks if re.search(r"SECURITY\s+DEFINER", b, re.I)):
    header = block.split(";", 1)[0]
    assert re.search(r"SET\s+search_path\s*=\s*pg_catalog,\s*portal", header, re.I), header[:180]
print(f"PASS: {len(paths)} ordered transactional migrations; {len(tables)} tables FORCE RLS; fixed SECURITY DEFINER search paths; no direct runtime-role writes")
