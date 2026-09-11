import importlib.util
from pathlib import Path

from sqlalchemy import CheckConstraint

from app.models.ldap_integration import LdapIntegrationConfig
from app.db import schema


MIGRATION_PATH = Path(__file__).parents[1] / "alembic" / "versions" / "20260910_002_add_ldap_integration_config.py"


def test_model_enforces_singleton_id_with_database_check_constraint():
    constraints = {
        item.name: str(item.sqltext)
        for item in LdapIntegrationConfig.__table__.constraints
        if isinstance(item, CheckConstraint)
    }
    assert constraints["ck_ldap_integration_config_singleton"] == "id = 1"


def test_migration_create_table_contains_singleton_constraint(monkeypatch):
    spec = importlib.util.spec_from_file_location("ldap_config_migration", MIGRATION_PATH)
    migration = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(migration)
    calls = []
    monkeypatch.setattr(migration, "op", type("Ops", (), {"create_table": lambda _self, *args: calls.append(args)})())
    monkeypatch.setattr(migration, "_table_exists", lambda: False)

    migration.upgrade()

    constraints = [item for item in calls[0] if isinstance(item, CheckConstraint)]
    assert len(constraints) == 1
    assert constraints[0].name == "ck_ldap_integration_config_singleton"
    assert str(constraints[0].sqltext) == "id = 1"


def test_runtime_schema_repairs_missing_ldap_config_columns(monkeypatch):
    statements = []

    class Inspector:
        def get_table_names(self): return ["ldap_integration_config"]
        def get_columns(self, _table): return [{"name": "id"}]
        def get_check_constraints(self, _table):
            return [{"name": "ck_ldap_integration_config_singleton"}]

    class Connection:
        def __enter__(self): return self
        def __exit__(self, *_args): pass
        def execute(self, statement): statements.append(str(statement))

    engine = type("Engine", (), {
        "dialect": type("Dialect", (), {"name": "mysql"})(),
        "begin": lambda _self: Connection(),
    })()
    monkeypatch.setattr(schema, "inspect", lambda _engine: Inspector())

    schema._ensure_ldap_integration_schema(engine)

    assert any("ADD COLUMN host" in statement for statement in statements)
    assert any("ADD COLUMN bind_password_encrypted" in statement for statement in statements)
    assert any("ADD COLUMN tested_fingerprint" in statement for statement in statements)
