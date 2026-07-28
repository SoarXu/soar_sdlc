"""add canonical project requirement pool iterations

Revision ID: 20260728_001
Revises: 20260727_001
Create Date: 2026-07-28 10:00:00.000000
"""

from collections.abc import Mapping, Sequence
from typing import Any, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260728_001"
down_revision: Union[str, None] = "20260727_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_POOL_NAME = "需求池"
_DEFAULT_LIFECYCLE_PHASE = "development"
_PROJECT_POOL_UNIQUE = "uq_projects_requirement_pool_iteration_id"
_PROJECT_POOL_FK = "fk_projects_requirement_pool_iteration"
_REQUIREMENT_ITERATION_FK = "fk_requirements_iteration"


def _columns(bind, table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _foreign_key_names(bind, table_name: str) -> set[str]:
    return {
        item["name"]
        for item in sa.inspect(bind).get_foreign_keys(table_name)
        if item.get("name")
    }


def _unique_constraint_names(bind, table_name: str) -> set[str]:
    return {
        item["name"]
        for item in sa.inspect(bind).get_unique_constraints(table_name)
        if item.get("name")
    }


def _format_audit_issues(issues: Sequence[Mapping[str, Any]]) -> str:
    entries: list[str] = []
    for issue in sorted(issues, key=lambda item: str(item["issue"])):
        ids = ",".join(str(value) for value in sorted({int(value) for value in issue["ids"]}))
        entries.append(f'{issue["issue"]}={ids}')
    return "Requirement pool migration audit failed: " + "; ".join(entries)


def _issue_ids(
    bind,
    statement: str,
    parameters: Mapping[str, Any] | None = None,
) -> list[int]:
    return [
        int(value)
        for value in bind.execute(sa.text(statement), parameters or {}).scalars().all()
    ]


def _collect_audit_issues(bind) -> list[dict[str, Any]]:
    issues_by_name = {
        "missing_pool_reference": _issue_ids(
            bind,
            "SELECT project.id FROM projects project "
            "LEFT JOIN iterations pool ON pool.id = project.requirement_pool_iteration_id "
            "WHERE project.requirement_pool_iteration_id IS NULL OR pool.id IS NULL "
            "ORDER BY project.id",
        ),
        "wrong_pool_flag": _issue_ids(
            bind,
            "SELECT project.id FROM projects project "
            "JOIN iterations pool ON pool.id = project.requirement_pool_iteration_id "
            "WHERE pool.is_requirement_pool <> :is_requirement_pool ORDER BY project.id",
            {"is_requirement_pool": 1},
        ),
        "pool_scope_mismatch": _issue_ids(
            bind,
            "SELECT project.id FROM projects project "
            "JOIN iterations pool ON pool.id = project.requirement_pool_iteration_id "
            "WHERE pool.is_requirement_pool = :is_requirement_pool AND ("
            "(SELECT COUNT(*) FROM iteration_projects membership "
            " WHERE membership.iteration_id = pool.id) <> 1 OR "
            "NOT EXISTS (SELECT 1 FROM iteration_projects membership "
            " WHERE membership.iteration_id = pool.id AND membership.project_id = project.id)"
            ") ORDER BY project.id",
            {"is_requirement_pool": 1},
        ),
        "null_requirement_iteration": _issue_ids(
            bind,
            "SELECT id FROM requirements WHERE iteration_id IS NULL ORDER BY id",
        ),
        "dangling_requirement_iteration": _issue_ids(
            bind,
            "SELECT requirement.id FROM requirements requirement "
            "LEFT JOIN iterations iteration_row ON iteration_row.id = requirement.iteration_id "
            "WHERE requirement.iteration_id IS NOT NULL AND iteration_row.id IS NULL "
            "ORDER BY requirement.id",
        ),
    }
    return [
        {"issue": issue, "ids": ids}
        for issue, ids in sorted(issues_by_name.items())
        if ids
    ]


def _audit_or_raise(bind) -> None:
    issues = _collect_audit_issues(bind)
    if issues:
        raise RuntimeError(_format_audit_issues(issues))


def _resolve_default_iteration_workflow(bind) -> tuple[int, int]:
    parameters = {
        "object_type": "iteration",
        "scope_type": "system",
        "is_default_template": 1,
        "enabled": 1,
    }
    valid_definition = bind.execute(
        sa.text(
            "SELECT definition.id, state.id AS initial_state_id "
            "FROM workflow_definitions definition "
            "JOIN workflow_states state ON state.id = definition.initial_state_id "
            "AND state.definition_id = definition.id AND state.enabled = :enabled "
            "WHERE definition.object_type = :object_type "
            "AND definition.scope_type = :scope_type "
            "AND definition.is_default_template = :is_default_template "
            "AND definition.enabled = :enabled "
            "ORDER BY definition.id DESC LIMIT 1"
        ),
        parameters,
    ).mappings().first()
    if valid_definition is not None:
        return int(valid_definition["id"]), int(valid_definition["initial_state_id"])

    definition = bind.execute(
        sa.text(
            "SELECT id, initial_state_id FROM workflow_definitions "
            "WHERE object_type = :object_type AND scope_type = :scope_type "
            "AND is_default_template = :is_default_template AND enabled = :enabled "
            "ORDER BY id DESC LIMIT 1"
        ),
        parameters,
    ).mappings().first()
    if definition is None:
        raise RuntimeError(
            "Cannot create requirement pools: no enabled default system iteration workflow"
        )

    definition_id = int(definition["id"])
    initial_state_id = definition["initial_state_id"]
    if initial_state_id is None:
        raise RuntimeError(
            f"Cannot create requirement pools: default system iteration workflow "
            f"{definition_id} has no initial state"
        )
    initial_state_id = int(initial_state_id)
    raise RuntimeError(
        f"Cannot create requirement pools: default system iteration workflow "
        f"{definition_id} has invalid or disabled initial state {initial_state_id}"
    )


def _project_rows(bind) -> list[Mapping[str, Any]]:
    projects = sa.Table("projects", sa.MetaData(), autoload_with=bind)
    lifecycle_expression = (
        projects.c.lifecycle_phase
        if "lifecycle_phase" in projects.c
        else sa.literal(_DEFAULT_LIFECYCLE_PHASE)
    ).label("lifecycle_phase")
    deleted_expression = (
        projects.c.deleted if "deleted" in projects.c else sa.literal(0)
    ).label("deleted")
    delete_time_expression = (
        projects.c.delete_time if "delete_time" in projects.c else sa.null()
    ).label("delete_time")
    return list(
        bind.execute(
            sa.select(
                projects.c.id,
                lifecycle_expression,
                deleted_expression,
                delete_time_expression,
                projects.c.requirement_pool_iteration_id,
            ).order_by(projects.c.id)
        ).mappings()
    )


def _create_project_requirement_pools(
    bind,
    workflow_definition_id: int,
    current_state_id: int,
) -> None:
    for project in _project_rows(bind):
        if project["requirement_pool_iteration_id"] is not None:
            continue
        project_id = int(project["id"])
        insert_result = bind.execute(
            sa.text(
                "INSERT INTO iterations ("
                "name, owner_id, start_date, end_date, actual_start_date, actual_end_date, "
                "is_requirement_pool, workflow_definition_id, current_state_id, lifecycle_phase, "
                "goal, creator_id, updater_id, deleted, delete_time"
                ") VALUES ("
                ":name, NULL, NULL, NULL, NULL, NULL, :is_requirement_pool, "
                ":workflow_definition_id, :current_state_id, :lifecycle_phase, "
                "NULL, NULL, NULL, :deleted, :delete_time)"
            ),
            {
                "name": _POOL_NAME,
                "is_requirement_pool": 1,
                "workflow_definition_id": workflow_definition_id,
                "current_state_id": current_state_id,
                "lifecycle_phase": project["lifecycle_phase"] or _DEFAULT_LIFECYCLE_PHASE,
                "deleted": int(project["deleted"] or 0),
                "delete_time": project["delete_time"],
            },
        )
        pool_id = insert_result.lastrowid
        if pool_id is None:
            raise RuntimeError(f"Cannot create requirement pool for project {project_id}: no pool ID")
        pool_id = int(pool_id)
        bind.execute(
            sa.text(
                "INSERT INTO iteration_projects (iteration_id, project_id) "
                "VALUES (:iteration_id, :project_id)"
            ),
            {"iteration_id": pool_id, "project_id": project_id},
        )
        bind.execute(
            sa.text(
                "UPDATE projects SET requirement_pool_iteration_id = :iteration_id "
                "WHERE id = :project_id"
            ),
            {"iteration_id": pool_id, "project_id": project_id},
        )


def _backfill_requirement_iterations(bind) -> None:
    bind.execute(
        sa.text(
            "UPDATE requirements SET iteration_id = ("
            "SELECT project.requirement_pool_iteration_id FROM projects project "
            "WHERE project.id = requirements.project_id"
            ") WHERE iteration_id IS NULL"
        )
    )


def _add_constraints(bind) -> None:
    bigint = sa.BigInteger()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("projects", recreate="always") as batch_op:
            batch_op.create_unique_constraint(
                _PROJECT_POOL_UNIQUE,
                ["requirement_pool_iteration_id"],
            )
            batch_op.create_foreign_key(
                _PROJECT_POOL_FK,
                "iterations",
                ["requirement_pool_iteration_id"],
                ["id"],
                ondelete="RESTRICT",
            )
        with op.batch_alter_table("requirements", recreate="always") as batch_op:
            batch_op.create_foreign_key(
                _REQUIREMENT_ITERATION_FK,
                "iterations",
                ["iteration_id"],
                ["id"],
                ondelete="RESTRICT",
            )
            batch_op.alter_column("iteration_id", existing_type=bigint, nullable=False)
        return

    if _PROJECT_POOL_UNIQUE not in _unique_constraint_names(bind, "projects"):
        op.create_unique_constraint(
            _PROJECT_POOL_UNIQUE,
            "projects",
            ["requirement_pool_iteration_id"],
        )
    project_foreign_keys = _foreign_key_names(bind, "projects")
    if _PROJECT_POOL_FK not in project_foreign_keys:
        op.create_foreign_key(
            _PROJECT_POOL_FK,
            "projects",
            "iterations",
            ["requirement_pool_iteration_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    if _REQUIREMENT_ITERATION_FK in _foreign_key_names(bind, "requirements"):
        op.drop_constraint(_REQUIREMENT_ITERATION_FK, "requirements", type_="foreignkey")
    op.alter_column(
        "requirements",
        "iteration_id",
        existing_type=bigint,
        nullable=False,
    )
    requirement_foreign_keys = _foreign_key_names(bind, "requirements")
    if _REQUIREMENT_ITERATION_FK not in requirement_foreign_keys:
        op.create_foreign_key(
            _REQUIREMENT_ITERATION_FK,
            "requirements",
            "iterations",
            ["iteration_id"],
            ["id"],
            ondelete="RESTRICT",
        )


def upgrade() -> None:
    bind = op.get_bind()
    if "is_requirement_pool" not in _columns(bind, "iterations"):
        op.add_column(
            "iterations",
            sa.Column(
                "is_requirement_pool",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("0"),
            ),
        )
    if "requirement_pool_iteration_id" not in _columns(bind, "projects"):
        op.add_column(
            "projects",
            sa.Column("requirement_pool_iteration_id", sa.BigInteger(), nullable=True),
        )

    workflow_definition_id, current_state_id = _resolve_default_iteration_workflow(bind)
    _create_project_requirement_pools(bind, workflow_definition_id, current_state_id)
    _backfill_requirement_iterations(bind)
    _audit_or_raise(bind)
    _add_constraints(bind)


def _remove_pool_rows(bind) -> None:
    parameters = {"is_requirement_pool": 1}
    bind.execute(
        sa.text(
            "DELETE FROM iteration_projects WHERE iteration_id IN ("
            "SELECT id FROM iterations WHERE is_requirement_pool = :is_requirement_pool)"
        ),
        parameters,
    )
    bind.execute(
        sa.text("DELETE FROM iterations WHERE is_requirement_pool = :is_requirement_pool"),
        parameters,
    )


def _drop_constraints_and_columns(bind) -> None:
    bigint = sa.BigInteger()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("requirements", recreate="always") as batch_op:
            if _REQUIREMENT_ITERATION_FK in _foreign_key_names(bind, "requirements"):
                batch_op.drop_constraint(_REQUIREMENT_ITERATION_FK, type_="foreignkey")
            batch_op.alter_column("iteration_id", existing_type=bigint, nullable=True)
        bind.execute(
            sa.text(
                "UPDATE requirements SET iteration_id = NULL WHERE iteration_id IN ("
                "SELECT id FROM iterations WHERE is_requirement_pool = :is_requirement_pool)"
            ),
            {"is_requirement_pool": 1},
        )
        with op.batch_alter_table("projects", recreate="always") as batch_op:
            if _PROJECT_POOL_FK in _foreign_key_names(bind, "projects"):
                batch_op.drop_constraint(_PROJECT_POOL_FK, type_="foreignkey")
            if _PROJECT_POOL_UNIQUE in _unique_constraint_names(bind, "projects"):
                batch_op.drop_constraint(_PROJECT_POOL_UNIQUE, type_="unique")
            batch_op.drop_column("requirement_pool_iteration_id")
        _remove_pool_rows(bind)
        with op.batch_alter_table("iterations", recreate="always") as batch_op:
            batch_op.drop_column("is_requirement_pool")
        return

    if _REQUIREMENT_ITERATION_FK in _foreign_key_names(bind, "requirements"):
        op.drop_constraint(_REQUIREMENT_ITERATION_FK, "requirements", type_="foreignkey")
    op.alter_column(
        "requirements",
        "iteration_id",
        existing_type=bigint,
        nullable=True,
    )
    bind.execute(
        sa.text(
            "UPDATE requirements SET iteration_id = NULL WHERE iteration_id IN ("
            "SELECT id FROM iterations WHERE is_requirement_pool = :is_requirement_pool)"
        ),
        {"is_requirement_pool": 1},
    )
    if _PROJECT_POOL_FK in _foreign_key_names(bind, "projects"):
        op.drop_constraint(_PROJECT_POOL_FK, "projects", type_="foreignkey")
    if _PROJECT_POOL_UNIQUE in _unique_constraint_names(bind, "projects"):
        op.drop_constraint(_PROJECT_POOL_UNIQUE, "projects", type_="unique")
    op.drop_column("projects", "requirement_pool_iteration_id")
    _remove_pool_rows(bind)
    op.drop_column("iterations", "is_requirement_pool")


def downgrade() -> None:
    _drop_constraints_and_columns(op.get_bind())
