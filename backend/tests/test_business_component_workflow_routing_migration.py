import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa

from app.db.session import Base
import app.models  # noqa: F401


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "20260727_001_business_component_workflow_routing.py"
)


def _migration_module():
    spec = importlib.util.spec_from_file_location(
        "business_component_workflow_routing",
        MIGRATION_PATH,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _OperationCapture:
    def __init__(self, bind):
        self.bind = bind
        self.created_tables = []
        self.created_indexes = []

    def get_bind(self):
        return self.bind

    def create_table(self, table_name, *args, **kwargs):
        self.created_tables.append(table_name)

    def create_index(self, name, table_name, columns):
        self.created_indexes.append((name, table_name, tuple(columns)))


class _EmptyInspector:
    def get_table_names(self):
        return []


def test_upgrade_keeps_fresh_install_creation_path(monkeypatch):
    migration = _migration_module()
    operations = _OperationCapture(object())
    monkeypatch.setattr(migration, "op", operations)
    monkeypatch.setattr(migration.sa, "inspect", lambda value: _EmptyInspector())

    migration.upgrade()

    assert operations.created_tables == [
        "business_components",
        "business_component_members",
        "business_component_transition_routes",
        "work_item_components",
        "workflow_migration_logs",
    ]
    assert len(operations.created_indexes) == 15


def test_upgrade_accepts_complete_tables_created_by_runtime_schema(monkeypatch):
    migration = _migration_module()
    engine = sa.create_engine("sqlite://")
    Base.metadata.create_all(engine)

    with engine.connect() as bind:
        operations = _OperationCapture(bind)
        monkeypatch.setattr(migration, "op", operations)

        migration.upgrade()

    assert operations.created_tables == []
    assert operations.created_indexes == []


class _IncompleteInspector:
    def get_columns(self, table_name):
        return [{"name": "id"}, {"name": "project_id"}]

    def get_indexes(self, table_name):
        return []

    def get_unique_constraints(self, table_name):
        return []

    def get_foreign_keys(self, table_name):
        return []


def test_existing_table_with_missing_contract_artifacts_is_rejected(monkeypatch):
    migration = _migration_module()
    bind = object()
    monkeypatch.setattr(migration.sa, "inspect", lambda value: _IncompleteInspector())

    with pytest.raises(
        RuntimeError,
        match=(
            "business_components.*missing indexes=.*project_id.*"
            "unique constraints=.*project_id,source_project_id.*"
            "foreign keys=.*project_id->projects"
        ),
    ):
        migration._assert_existing_table_contract(
            bind,
            "business_components",
            ("id", "project_id", "source_project_id"),
            (("project_id",),),
            (("project_id", "source_project_id"),),
            (("project_id", "projects"),),
        )
