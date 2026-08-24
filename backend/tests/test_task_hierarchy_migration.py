from pathlib import Path

from app.models.task import Task
from app.views.task_view import TaskCreate, TaskRead, TaskUpdate


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "20260822_005_task_hierarchy.py"
)


def test_task_parent_relation_is_nullable_self_reference_and_exposed_read_only():
    parent_column = Task.__table__.c.parent_task_id

    assert parent_column.nullable is True
    assert parent_column.index is True
    assert {foreign_key.target_fullname for foreign_key in parent_column.foreign_keys} == {"tasks.id"}
    assert {foreign_key.ondelete for foreign_key in parent_column.foreign_keys} == {"RESTRICT"}
    assert "parent_task_id" in TaskCreate.model_fields
    assert "parent_task_id" not in TaskUpdate.model_fields
    assert "parent_task_id" in TaskRead.model_fields
    assert "parent_task" in TaskRead.model_fields
    assert "direct_child_count" in TaskRead.model_fields


def test_task_hierarchy_migration_uses_current_revision_and_mysql_safe_self_parent_guard():
    assert MIGRATION_PATH.exists()

    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'revision = "20260822_005"' in source
    assert 'down_revision = "20260822_004"' in source
    assert "parent_task_id" in source
    assert "op.create_foreign_key(" in source
    assert '"tasks"' in source
    assert 'ondelete="RESTRICT"' in source
    assert "CREATE TRIGGER" in source
    assert "NEW.parent_task_id = NEW.id" in source
    assert "SIGNAL SQLSTATE '45000'" in source
