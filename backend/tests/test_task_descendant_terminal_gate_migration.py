from pathlib import Path


def test_task_descendant_terminal_gate_migration_reconciles_only_managed_task_workflows():
    migration = Path(__file__).parents[1] / "alembic" / "versions" / "20260822_006_task_descendant_terminal_gate.py"

    assert migration.exists()
    source = migration.read_text(encoding="utf-8")
    assert 'revision = "20260822_006"' in source
    assert 'down_revision = "20260822_005"' in source
    assert "reconcile_managed_task_terminal_gates" in source
