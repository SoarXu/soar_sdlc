"""add task parent hierarchy

Revision ID: 20260822_005
Revises: 20260822_004
Create Date: 2026-08-24 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260822_005"
down_revision = "20260822_004"
branch_labels = None
depends_on = None


_INDEX_NAME = "ix_tasks_parent_task_id"
_FOREIGN_KEY_NAME = "fk_tasks_parent_task_id"
_CHECK_NAME = "ck_tasks_parent_task_not_self"
_INSERT_TRIGGER_NAME = "trg_tasks_parent_not_self_insert"
_UPDATE_TRIGGER_NAME = "trg_tasks_parent_not_self_update"


def upgrade() -> None:
    bind = op.get_bind()
    if "parent_task_id" not in _column_names(bind):
        op.add_column("tasks", sa.Column("parent_task_id", sa.BigInteger(), nullable=True))
    if _INDEX_NAME not in _index_names(bind):
        op.create_index(_INDEX_NAME, "tasks", ["parent_task_id"], unique=False)
    if _FOREIGN_KEY_NAME not in _foreign_key_names(bind):
        op.create_foreign_key(
            _FOREIGN_KEY_NAME,
            "tasks",
            "tasks",
            ["parent_task_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    if bind.dialect.name == "mysql":
        _ensure_mysql_self_parent_triggers(bind)
    elif _CHECK_NAME not in _check_constraint_names(bind):
        op.create_check_constraint(
            _CHECK_NAME,
            "tasks",
            "parent_task_id IS NULL OR parent_task_id <> id",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        _drop_mysql_self_parent_triggers(bind)
    elif _CHECK_NAME in _check_constraint_names(bind):
        op.drop_constraint(_CHECK_NAME, "tasks", type_="check")
    if _FOREIGN_KEY_NAME in _foreign_key_names(bind):
        op.drop_constraint(_FOREIGN_KEY_NAME, "tasks", type_="foreignkey")
    if _INDEX_NAME in _index_names(bind):
        op.drop_index(_INDEX_NAME, table_name="tasks")
    if "parent_task_id" in _column_names(bind):
        op.drop_column("tasks", "parent_task_id")


def _column_names(bind) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns("tasks")}


def _index_names(bind) -> set[str]:
    return {index["name"] for index in sa.inspect(bind).get_indexes("tasks")}


def _foreign_key_names(bind) -> set[str]:
    return {foreign_key["name"] for foreign_key in sa.inspect(bind).get_foreign_keys("tasks")}


def _check_constraint_names(bind) -> set[str]:
    return {constraint["name"] for constraint in sa.inspect(bind).get_check_constraints("tasks")}


def _ensure_mysql_self_parent_triggers(bind) -> None:
    trigger_names = _trigger_names(bind)
    if _INSERT_TRIGGER_NAME not in trigger_names:
        op.execute(
            f"""
            CREATE TRIGGER {_INSERT_TRIGGER_NAME}
            AFTER INSERT ON tasks
            FOR EACH ROW
            BEGIN
                IF NEW.parent_task_id IS NOT NULL AND NEW.parent_task_id = NEW.id THEN
                    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Task cannot be its own parent';
                END IF;
            END
            """
        )
    if _UPDATE_TRIGGER_NAME not in trigger_names:
        op.execute(
            f"""
            CREATE TRIGGER {_UPDATE_TRIGGER_NAME}
            BEFORE UPDATE ON tasks
            FOR EACH ROW
            BEGIN
                IF NEW.parent_task_id IS NOT NULL AND NEW.parent_task_id = NEW.id THEN
                    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Task cannot be its own parent';
                END IF;
            END
            """
        )


def _drop_mysql_self_parent_triggers(bind) -> None:
    for trigger_name in (_UPDATE_TRIGGER_NAME, _INSERT_TRIGGER_NAME):
        if trigger_name in _trigger_names(bind):
            op.execute(f"DROP TRIGGER {trigger_name}")


def _trigger_names(bind) -> set[str]:
    return {
        row[0]
        for row in bind.execute(
            sa.text(
                "SELECT TRIGGER_NAME FROM information_schema.TRIGGERS "
                "WHERE TRIGGER_SCHEMA = DATABASE() AND EVENT_OBJECT_TABLE = 'tasks'"
            )
        ).all()
    }
