"""migrate requirement pools to real iterations and remove pool identity

Revision ID: 20260811_002
Revises: 20260811_001
Create Date: 2026-08-11 17:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260811_002"
down_revision: Union[str, None] = "20260811_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(bind, table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _constraint_names_for_columns(
    bind, table_name: str, kind: str, column_names: tuple[str, ...]
) -> list[str]:
    inspector = sa.inspect(bind)
    rows = (
        inspector.get_foreign_keys(table_name)
        if kind == "foreign_key"
        else inspector.get_unique_constraints(table_name)
    )
    reflected_key = "constrained_columns" if kind == "foreign_key" else "column_names"
    return [
        row["name"]
        for row in rows
        if row.get("name") and tuple(row.get(reflected_key) or ()) == column_names
    ]


def _default_iteration_workflow(bind) -> tuple[int, int]:
    row = bind.execute(
        sa.text(
            "SELECT definition.id, definition.initial_state_id "
            "FROM workflow_definitions definition "
            "JOIN workflow_states state ON state.id = definition.initial_state_id "
            "WHERE definition.object_type = 'iteration' "
            "AND definition.scope_type = 'system' "
            "AND definition.is_default_template = 1 "
            "AND definition.enabled = 1 AND state.enabled = 1 "
            "ORDER BY definition.id DESC LIMIT 1"
        )
    ).mappings().first()
    if not row:
        raise RuntimeError("No enabled default iteration workflow is available")
    return int(row["id"]), int(row["initial_state_id"])


def _create_target_iteration(bind, project_id: int, lifecycle_phase: str | None) -> int:
    definition_id, state_id = _default_iteration_workflow(bind)
    result = bind.execute(
        sa.text(
            "INSERT INTO iterations (name, is_requirement_pool, workflow_definition_id, "
            "current_state_id, lifecycle_phase, deleted) "
            "VALUES (:name, 0, :definition_id, :state_id, :lifecycle_phase, 0)"
        ),
        {
            "name": "待规划迭代",
            "definition_id": definition_id,
            "state_id": state_id,
            "lifecycle_phase": lifecycle_phase or "development",
        },
    )
    target_id = result.lastrowid
    if target_id is None:
        raise RuntimeError(f"Could not create fallback iteration for project {project_id}")
    bind.execute(
        sa.text(
            "INSERT INTO iteration_projects (iteration_id, project_id) "
            "VALUES (:iteration_id, :project_id)"
        ),
        {"iteration_id": int(target_id), "project_id": project_id},
    )
    return int(target_id)


def _target_iteration_id(bind, project_id: int, pool_id: int, lifecycle_phase: str | None) -> int:
    row = bind.execute(
        sa.text(
            "SELECT iteration_row.id FROM iterations iteration_row "
            "JOIN iteration_projects membership ON membership.iteration_id = iteration_row.id "
            "JOIN workflow_states state ON state.id = iteration_row.current_state_id "
            "WHERE membership.project_id = :project_id AND iteration_row.id <> :pool_id "
            "AND iteration_row.deleted = 0 AND state.category IN ('start', 'normal', 'in_progress') "
            "ORDER BY CASE WHEN state.category IN ('normal', 'in_progress') THEN 0 ELSE 1 END, "
            "iteration_row.id ASC LIMIT 1"
        ),
        {"project_id": project_id, "pool_id": pool_id},
    ).scalar_one_or_none()
    return int(row) if row is not None else _create_target_iteration(bind, project_id, lifecycle_phase)


def _move_pool_items(bind, project_id: int, pool_id: int, target_id: int) -> None:
    inspector = sa.inspect(bind)
    has_history = "work_item_iteration_history" in inspector.get_table_names()
    for object_type, table_name in (("requirement", "requirements"), ("task", "tasks"), ("bug", "bugs")):
        rows = bind.execute(
            sa.text(
                f"SELECT id FROM {table_name} WHERE project_id = :project_id "
                "AND iteration_id = :pool_id"
            ),
            {"project_id": project_id, "pool_id": pool_id},
        ).scalars().all()
        if not rows:
            continue
        bind.execute(
            sa.text(
                f"UPDATE {table_name} SET iteration_id = :target_id "
                "WHERE project_id = :project_id AND iteration_id = :pool_id"
            ),
            {"target_id": target_id, "project_id": project_id, "pool_id": pool_id},
        )
        if not has_history:
            continue
        for object_id in rows:
            bind.execute(
                sa.text(
                    "UPDATE work_item_iteration_history SET left_at = CURRENT_TIMESTAMP, "
                    "leave_reason = :reason, migrated = 1 "
                    "WHERE object_type = :object_type AND object_id = :object_id "
                    "AND iteration_id = :pool_id AND left_at IS NULL"
                ),
                {
                    "reason": "requirement_pool_removed",
                    "object_type": object_type,
                    "object_id": int(object_id),
                    "pool_id": pool_id,
                },
            )
            bind.execute(
                sa.text(
                    "INSERT INTO work_item_iteration_history "
                    "(object_type, object_id, iteration_id, enter_reason, migrated) "
                    "VALUES (:object_type, :object_id, :target_id, :reason, 1)"
                ),
                {
                    "object_type": object_type,
                    "object_id": int(object_id),
                    "target_id": target_id,
                    "reason": "requirement_pool_removed",
                },
            )


def upgrade() -> None:
    bind = op.get_bind()
    if "requirement_pool_iteration_id" not in _columns(bind, "projects"):
        return
    projects = bind.execute(
        sa.text(
            "SELECT id, requirement_pool_iteration_id FROM projects "
            "WHERE requirement_pool_iteration_id IS NOT NULL ORDER BY id"
        )
    ).mappings().all()
    for project in projects:
        project_id = int(project["id"])
        pool_id = int(project["requirement_pool_iteration_id"])
        lifecycle_phase = bind.execute(
            sa.text("SELECT lifecycle_phase FROM iterations WHERE id = :id"), {"id": pool_id}
        ).scalar_one_or_none()
        target_id = _target_iteration_id(bind, project_id, pool_id, lifecycle_phase)
        _move_pool_items(bind, project_id, pool_id, target_id)
        bind.execute(
            sa.text(
                "UPDATE projects SET requirement_pool_iteration_id = NULL WHERE id = :project_id"
            ),
            {"project_id": project_id},
        )
        bind.execute(
            sa.text("DELETE FROM iteration_projects WHERE iteration_id = :pool_id"),
            {"pool_id": pool_id},
        )
        bind.execute(sa.text("DELETE FROM iterations WHERE id = :pool_id"), {"pool_id": pool_id})

    target_columns = ("requirement_pool_iteration_id",)
    foreign_keys = _constraint_names_for_columns(bind, "projects", "foreign_key", target_columns)
    unique_constraints = _constraint_names_for_columns(bind, "projects", "unique", target_columns)
    with op.batch_alter_table("projects") as batch:
        for name in foreign_keys:
            batch.drop_constraint(name, type_="foreignkey")
        for name in unique_constraints:
            batch.drop_constraint(name, type_="unique")
        batch.drop_column("requirement_pool_iteration_id")
    if "is_requirement_pool" in _columns(bind, "iterations"):
        with op.batch_alter_table("iterations") as batch:
            batch.drop_column("is_requirement_pool")


def downgrade() -> None:
    bind = op.get_bind()
    if "is_requirement_pool" not in _columns(bind, "iterations"):
        op.add_column(
            "iterations",
            sa.Column("is_requirement_pool", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if "requirement_pool_iteration_id" not in _columns(bind, "projects"):
        op.add_column(
            "projects", sa.Column("requirement_pool_iteration_id", sa.BigInteger(), nullable=True)
        )
