from pathlib import Path
import importlib.util

from app.models.workflow_definition import WorkflowState
from app.views.workflow_definition_view import WorkflowStateRead


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "20260822_002_work_item_state_roles.py"
)


def test_state_role_is_persisted_and_exposed_by_workflow_contracts():
    assert MIGRATION_PATH.exists()
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'revision = "20260822_002"' in source
    assert 'down_revision = "20260822_001"' in source
    assert "state_role" in source

    column = WorkflowState.__table__.c.state_role
    assert column.nullable is True

    state = WorkflowState(
        id=1,
        definition_id=1,
        status_name="待分派",
        category="start",
        color="#6b7280",
        x=0,
        y=0,
        sort_order=10,
        enabled=True,
        state_role="unassigned",
    )
    assert WorkflowStateRead.model_validate(state).state_role == "unassigned"


def test_upgrade_skips_existing_state_role_column_and_index(monkeypatch):
    migration = _load_migration_module()
    calls = []

    class Inspector:
        def get_columns(self, table_name):
            assert table_name == "workflow_states"
            return [{"name": "state_role"}]

        def get_indexes(self, table_name):
            assert table_name == "workflow_states"
            return [{"name": "ix_workflow_states_definition_state_role"}]

    class Operation:
        def get_bind(self):
            return object()

        def add_column(self, *args):
            calls.append(("add_column", args))

        def create_index(self, *args, **kwargs):
            calls.append(("create_index", args, kwargs))

    monkeypatch.setattr(migration, "op", Operation())
    monkeypatch.setattr(migration.sa, "inspect", lambda _bind: Inspector())

    migration.upgrade()

    assert calls == []


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("work_item_state_roles_migration", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
