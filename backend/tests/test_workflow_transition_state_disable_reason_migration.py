from pathlib import Path
import importlib.util

from app.models.workflow_definition import WorkflowTransition
from app.views.workflow_definition_view import WorkflowTransitionRead, WorkflowTransitionSave


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "20260822_001_workflow_transition_state_disable_reason.py"
)


def test_transition_state_disable_reason_is_persisted_and_exposed():
    assert MIGRATION_PATH.exists()
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'revision = "20260822_001"' in source
    assert 'down_revision = "20260819_008"' in source
    assert "auto_disabled_by_state" in source

    column = WorkflowTransition.__table__.c.auto_disabled_by_state
    assert column.nullable is False
    assert column.default.arg is False
    assert column.server_default.arg.text in {"0", "false", "FALSE"}

    transition = WorkflowTransition(
        id=1,
        definition_id=1,
        action_key="next",
        action_name="下一步",
        from_state_id=1,
        to_state_id=2,
        allowed_roles="",
        enabled=True,
        auto_disabled_by_state=False,
        sort_order=100,
    )
    assert WorkflowTransitionRead.model_validate(transition).auto_disabled_by_state is False
    assert WorkflowTransitionSave(
        action_name="下一步",
        from_state_id=1,
        to_state_id=2,
        auto_disabled_by_state=True,
    ).auto_disabled_by_state is True


def test_upgrade_skips_existing_transition_disable_reason_column(monkeypatch):
    migration = _load_migration_module()
    calls = []

    class Inspector:
        def get_columns(self, table_name):
            assert table_name == "workflow_transitions"
            return [{"name": "auto_disabled_by_state"}]

    class Operation:
        def get_bind(self):
            return object()

        def add_column(self, *args):
            calls.append(args)

    monkeypatch.setattr(migration, "op", Operation())
    monkeypatch.setattr(migration.sa, "inspect", lambda _bind: Inspector())

    migration.upgrade()

    assert calls == []


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("workflow_transition_disable_reason_migration", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
