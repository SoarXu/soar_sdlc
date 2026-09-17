import importlib.util
import inspect
from pathlib import Path

from app.db import schema


MIGRATION_PATH = Path(__file__).parents[1] / "alembic" / "versions" / "20260910_001_add_ldap_user_fields.py"


class RecordingOperations:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def record(*args, **kwargs):
            self.calls.append((name, args, kwargs))

        return record

    def get_bind(self):
        return object()


class ExistingInspector:
    def get_columns(self, _table_name):
        return [{"name": name} for name in {
            "employee_no", "auth_source", "ldap_external_id", "ldap_dn",
            "ldap_last_synced_at", "active_employee_no",
        }]

    def get_indexes(self, _table_name):
        return [
            {"name": "uq_users_active_employee_no", "column_names": ["active_employee_no"], "unique": True},
            {"name": "uq_users_ldap_external_id", "column_names": ["ldap_external_id"], "unique": True},
        ]


def _migration_module():
    spec = importlib.util.spec_from_file_location("ldap_user_fields_migration", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_upgrade_adds_ldap_columns_active_employee_generated_key_and_backfills_local(monkeypatch):
    migration = _migration_module()
    operations = RecordingOperations()
    monkeypatch.setattr(migration, "op", operations)

    migration.upgrade()

    added_columns = {args[1].name: args[1] for name, args, _kwargs in operations.calls if name == "add_column"}
    assert {"employee_no", "auth_source", "ldap_external_id", "ldap_dn", "ldap_last_synced_at", "active_employee_no"} <= set(added_columns)
    assert added_columns["active_employee_no"].computed is not None
    expression = str(added_columns["active_employee_no"].computed.sqltext)
    assert "deleted = 0" in expression
    assert "is_active = 1" in expression
    assert (
        "create_index",
        ("uq_users_active_employee_no", "users", ["active_employee_no"]),
        {"unique": True},
    ) in operations.calls
    executed_sql = "\n".join(str(args[0]) for name, args, _kwargs in operations.calls if name == "execute")
    assert "UPDATE users SET auth_source = 'local'" in executed_sql


def test_downgrade_removes_indexes_and_all_ldap_user_columns(monkeypatch):
    migration = _migration_module()
    operations = RecordingOperations()
    monkeypatch.setattr(migration, "op", operations)

    migration.downgrade()

    assert ("drop_index", ("uq_users_active_employee_no",), {"table_name": "users"}) in operations.calls
    dropped_columns = {args[1] for name, args, _kwargs in operations.calls if name == "drop_column"}
    assert dropped_columns == {
        "active_employee_no",
        "ldap_last_synced_at",
        "ldap_dn",
        "ldap_external_id",
        "auth_source",
        "employee_no",
    }


def test_runtime_schema_installs_active_employee_number_constraint():
    helper_source = inspect.getsource(schema._ensure_ldap_user_identity_schema)
    runtime_source = inspect.getsource(schema.ensure_runtime_schema)

    assert "active_employee_no" in helper_source
    assert "uq_users_active_employee_no" in helper_source
    assert "deleted = 0 AND is_active = 1" in helper_source
    assert 'DEFAULT \'local\'' in helper_source
    assert "DEFAULT ''local'" not in helper_source
    assert "_ensure_ldap_user_identity_schema(engine)" in runtime_source


def test_online_upgrade_skips_ldap_user_schema_that_runtime_repair_already_installed(monkeypatch):
    migration = _migration_module()
    operations = RecordingOperations()
    monkeypatch.setattr(migration, "op", operations)
    monkeypatch.setattr(migration.context, "is_offline_mode", lambda: False)
    monkeypatch.setattr(migration.sa, "inspect", lambda _bind: ExistingInspector())

    migration.upgrade()

    schema_calls = {"add_column", "create_index", "create_unique_constraint"}
    assert not [call for call in operations.calls if call[0] in schema_calls]
    assert any(call[0] == "execute" for call in operations.calls)


def test_online_downgrade_skips_schema_objects_that_are_already_absent(monkeypatch):
    migration = _migration_module()
    operations = RecordingOperations()
    monkeypatch.setattr(migration, "op", operations)
    monkeypatch.setattr(migration.context, "is_offline_mode", lambda: False)
    monkeypatch.setattr(migration.sa, "inspect", lambda _bind: type("EmptyInspector", (), {
        "get_columns": lambda self, _table: [],
        "get_indexes": lambda self, _table: [],
    })())

    migration.downgrade()

    assert operations.calls == []
