import importlib.util
import inspect
from pathlib import Path

from sqlalchemy import BigInteger

from app.db import schema
from app.models.ldap_sync import LdapSyncItem, LdapSyncRun


MIGRATION_PATH = Path(__file__).parents[1] / "alembic" / "versions" / "20260910_003_add_ldap_sync_audit.py"


def test_sync_audit_models_capture_decisions_and_results_without_credentials():
    run = LdapSyncRun.__table__
    item = LdapSyncItem.__table__
    assert isinstance(run.c.id.type, BigInteger)
    assert {"initiated_by_user_id", "status", "total_count", "created_count", "bound_count", "updated_count", "skipped_count", "failed_count"} <= set(run.c.keys())
    assert {"run_id", "external_id", "decision", "status", "user_id", "message"} <= set(item.c.keys())
    forbidden = {"password", "bind_password", "payload", "raw_data"}
    assert forbidden.isdisjoint(run.c.keys())
    assert forbidden.isdisjoint(item.c.keys())


def test_sync_audit_migration_is_chained_and_runtime_repair_is_registered():
    assert MIGRATION_PATH.exists()
    spec = importlib.util.spec_from_file_location("ldap_sync_migration", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.down_revision == "20260910_002"
    source = inspect.getsource(schema.ensure_runtime_schema)
    assert "_ensure_ldap_sync_audit_schema(engine)" in source


def test_sync_migration_offline_sql_contains_both_audit_tables():
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "ldap_sync_runs" in source
    assert "ldap_sync_items" in source
    assert "bind_password" not in source
