from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"


def sql_files():
    return sorted(MIGRATIONS.glob("[0-9][0-9][0-9][0-9]_*.sql"))


def all_sql():
    return "\n".join(path.read_text() for path in sql_files())


def test_migrations_are_strictly_ordered_and_transactional():
    files = sql_files()
    assert [p.name[:4] for p in files] == [f"{n:04d}" for n in range(1, 10)]
    for path in files:
        text = path.read_text().strip()
        assert text.startswith("BEGIN;") and text.endswith("COMMIT;")


def test_every_portal_table_enables_and_forces_rls():
    sql = all_sql()
    tables = set(re.findall(r"CREATE TABLE portal\.([a-z0-9_]+)", sql, re.I))
    rls = (MIGRATIONS / "0005_restrictive_rls.sql").read_text()
    for table in tables:
        assert f"ALTER TABLE portal.{table} ENABLE ROW LEVEL SECURITY;" in rls, table
        assert f"ALTER TABLE portal.{table} FORCE ROW LEVEL SECURITY;" in rls, table
    assert "USING (true)" not in rls.lower()
    assert "WITH CHECK (true)" not in rls.lower()


def test_api_and_worker_have_no_direct_table_write_grants():
    sql = all_sql().lower()
    assert "revoke all on all tables in schema portal from portal_api, portal_worker" in sql
    dangerous = re.findall(r"grant\s+(insert|update|delete|truncate|references|trigger|all)\b[^;]*\bto\s+(portal_api|portal_worker)\b", sql)
    assert dangerous == []


def test_security_definer_functions_pin_search_path_and_public_execute_is_revoked():
    sql = all_sql()
    functions = re.split(r"(?=CREATE OR REPLACE FUNCTION portal\.)", sql, flags=re.I)[1:]
    definer_blocks = [block for block in functions if re.search(r"SECURITY\s+DEFINER", block, re.I)]
    assert definer_blocks
    for block in definer_blocks:
        header = block.split(";", 1)[0]
        assert re.search(r"SET\s+search_path\s*=\s*pg_catalog,\s*portal", header, re.I), header[:160]
    assert "REVOKE ALL ON ALL FUNCTIONS IN SCHEMA portal FROM PUBLIC" in sql


def test_server_scope_object_keys_receipts_and_outbound_only_guards_exist():
    sql = all_sql()
    assert "portal.current_household_ids()" in sql
    assert "portal.current_entity_scope()" in sql
    assert "portal.can_entity" in sql
    assert "quarantine/" in sql and "clean/" in sql
    assert "receipt_sha256" in sql and "deny_update_delete" in sql
    assert "execution_state" in sql and "not_executable" in sql
    assert "outbound_only" in sql
    assert "money_movement" in sql and "trade" in sql


def test_worker_rpcs_are_role_gated_and_retryable():
    text = (MIGRATIONS / "0009_worker_immutability.sql").read_text()
    assert text.count("portal.assert_worker()") >= 10
    assert "FOR UPDATE SKIP LOCKED" in text
    assert "worker_retry_scan" in text and "worker_retry_delete" in text and "worker_retry_outbox" in text
    assert "worker_activate_due_policies" in text
