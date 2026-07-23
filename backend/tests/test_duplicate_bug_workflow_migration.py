import importlib.util
from pathlib import Path

from sqlalchemy import create_engine, text


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "20260723_001_disable_debug_bug_workflow.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("duplicate_bug_workflow_migration", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_disables_only_confirmed_debug_duplicate(monkeypatch):
    migration = _load_migration()
    engine = create_engine("sqlite://")
    with engine.begin() as bind:
        bind.execute(text(
            "CREATE TABLE workflow_definitions ("
            "id INTEGER PRIMARY KEY, name VARCHAR(150), object_type VARCHAR(32), "
            "scope_type VARCHAR(32), scope_id INTEGER, enabled BOOLEAN)"
        ))
        bind.execute(text(
            "INSERT INTO workflow_definitions (id, name, object_type, scope_type, scope_id, enabled) VALUES "
            "(33, '默认 Bug 工作流', 'bug', 'assignee_rule_config', 1, 1), "
            "(466, 'debug-def', 'bug', 'assignee_rule_config', 1, 1), "
            "(467, 'debug-def', 'bug', 'assignee_rule_config', 2, 1)"
        ))
        monkeypatch.setattr(migration.op, "get_bind", lambda: bind)

        migration.upgrade()

        enabled_by_id = dict(bind.execute(text("SELECT id, enabled FROM workflow_definitions")).all())

    assert enabled_by_id == {33: 1, 466: 0, 467: 1}
