"""add business component workflow routing tables

Revision ID: 20260727_001
Revises: 20260722_004, 20260723_001
Create Date: 2026-07-27 10:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "20260727_001"
down_revision: Union[str, tuple[str, str], None] = ("20260722_004", "20260723_001")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _assert_existing_table_contract(
    bind,
    table_name: str,
    required_columns: tuple[str, ...],
    required_indexes: tuple[tuple[str, ...], ...],
    required_unique_constraints: tuple[tuple[str, ...], ...],
    required_foreign_keys: tuple[tuple[str, str], ...],
) -> None:
    """Reject runtime-created tables that do not satisfy this migration's contract."""
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
    existing_indexes = {
        tuple(index["column_names"] or [])
        for index in inspector.get_indexes(table_name)
    }
    existing_unique_constraints = {
        tuple(constraint["column_names"] or [])
        for constraint in inspector.get_unique_constraints(table_name)
    }
    existing_unique_constraints.update(
        tuple(index["column_names"] or [])
        for index in inspector.get_indexes(table_name)
        if index.get("unique")
    )
    existing_foreign_keys = {
        (tuple(foreign_key["constrained_columns"] or []), foreign_key["referred_table"])
        for foreign_key in inspector.get_foreign_keys(table_name)
    }

    missing_columns = sorted(set(required_columns) - existing_columns)
    missing_indexes = sorted(set(required_indexes) - existing_indexes)
    missing_unique_constraints = sorted(
        set(required_unique_constraints) - existing_unique_constraints
    )
    missing_foreign_keys = sorted(
        set((column, referred_table) for column, referred_table in required_foreign_keys)
        - {(columns[0], referred_table) for columns, referred_table in existing_foreign_keys if len(columns) == 1}
    )

    if not any((missing_columns, missing_indexes, missing_unique_constraints, missing_foreign_keys)):
        return

    issues = []
    if missing_columns:
        issues.append(f"missing columns={','.join(missing_columns)}")
    if missing_indexes:
        issues.append(
            "missing indexes=" + ";".join(",".join(columns) for columns in missing_indexes)
        )
    if missing_unique_constraints:
        issues.append(
            "missing unique constraints="
            + ";".join(",".join(columns) for columns in missing_unique_constraints)
        )
    if missing_foreign_keys:
        issues.append(
            "missing foreign keys="
            + ";".join(f"{column}->{referred_table}" for column, referred_table in missing_foreign_keys)
        )
    raise RuntimeError(
        f"Existing table {table_name} is incompatible with migration {revision}: "
        + "; ".join(issues)
    )


def upgrade() -> None:
    bind = op.get_bind()
    existing_tables = set(sa.inspect(bind).get_table_names())

    if "business_components" in existing_tables:
        _assert_existing_table_contract(
            bind,
            "business_components",
            (
                "id", "project_id", "source_project_id", "source_project_name_snapshot",
                "name", "description", "owner_id", "workflow_scheme_id", "enabled",
                "create_time", "update_time",
            ),
            (
                ("project_id",), ("source_project_id",), ("owner_id",),
                ("workflow_scheme_id",),
            ),
            (("project_id", "source_project_id"),),
            (
                ("project_id", "projects"), ("source_project_id", "projects"),
                ("owner_id", "users"), ("workflow_scheme_id", "assignee_rule_configs"),
            ),
        )
    else:
        op.create_table(
        "business_components",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("source_project_id", sa.BigInteger(), nullable=True),
        sa.Column("source_project_name_snapshot", sa.String(length=150), nullable=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.BigInteger(), nullable=True),
        sa.Column("workflow_scheme_id", sa.BigInteger(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("update_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name="fk_business_components_project", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_project_id"], ["projects.id"], name="fk_business_components_source_project", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name="fk_business_components_owner", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["workflow_scheme_id"], ["assignee_rule_configs.id"], name="fk_business_components_workflow_scheme", ondelete="RESTRICT"),
        sa.UniqueConstraint("project_id", "source_project_id", name="uk_business_component_project_source"),
        )
        op.create_index("ix_business_components_project_id", "business_components", ["project_id"])
        op.create_index("ix_business_components_source_project_id", "business_components", ["source_project_id"])
        op.create_index("ix_business_components_owner_id", "business_components", ["owner_id"])
        op.create_index("ix_business_components_workflow_scheme_id", "business_components", ["workflow_scheme_id"])

    if "business_component_members" in existing_tables:
        _assert_existing_table_contract(
            bind,
            "business_component_members",
            (
                "id", "component_id", "user_id", "component_role", "enabled",
                "effective_from", "effective_to", "create_time", "update_time",
            ),
            (("component_id",), ("user_id",)),
            (("component_id", "user_id"),),
            (("component_id", "business_components"), ("user_id", "users")),
        )
    else:
        op.create_table(
        "business_component_members",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("component_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("component_role", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("effective_from", sa.DateTime(), nullable=True),
        sa.Column("effective_to", sa.DateTime(), nullable=True),
        sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("update_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["component_id"], ["business_components.id"], name="fk_component_members_component", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_component_members_user", ondelete="RESTRICT"),
        sa.UniqueConstraint("component_id", "user_id", name="uk_business_component_member"),
        )
        op.create_index("ix_business_component_members_component_id", "business_component_members", ["component_id"])
        op.create_index("ix_business_component_members_user_id", "business_component_members", ["user_id"])

    if "business_component_transition_routes" in existing_tables:
        _assert_existing_table_contract(
            bind,
            "business_component_transition_routes",
            (
                "id", "component_id", "object_type", "transition_id", "eligible_member_mode",
                "eligible_roles", "eligible_user_ids", "next_owner_mode", "next_owner_roles",
                "next_owner_user_id", "fallback_mode", "enabled", "create_time", "update_time",
            ),
            (
                ("component_id",), ("object_type",), ("transition_id",),
            ),
            (("component_id", "object_type", "transition_id"),),
            (("component_id", "business_components"), ("transition_id", "workflow_transitions")),
        )
    else:
        op.create_table(
        "business_component_transition_routes",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("component_id", sa.BigInteger(), nullable=False),
        sa.Column("object_type", sa.String(length=32), nullable=False),
        sa.Column("transition_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("eligible_member_mode", sa.String(length=32), nullable=False, server_default="component_role"),
        sa.Column("eligible_roles", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("eligible_user_ids", sa.String(length=1000), nullable=False, server_default=""),
        sa.Column("next_owner_mode", sa.String(length=32), nullable=False, server_default="component_role"),
        sa.Column("next_owner_roles", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("next_owner_user_id", sa.BigInteger(), nullable=True),
        sa.Column("fallback_mode", sa.String(length=32), nullable=False, server_default="pending_assignment"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("update_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["component_id"], ["business_components.id"], name="fk_component_routes_component", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["transition_id"], ["workflow_transitions.id"], name="fk_component_routes_transition", ondelete="RESTRICT"),
        sa.UniqueConstraint("component_id", "object_type", "transition_id", name="uk_component_transition_route"),
        )
        op.create_index("ix_component_routes_component_id", "business_component_transition_routes", ["component_id"])
        op.create_index("ix_component_routes_object_type", "business_component_transition_routes", ["object_type"])
        op.create_index("ix_component_routes_transition_id", "business_component_transition_routes", ["transition_id"])

    if "work_item_components" in existing_tables:
        _assert_existing_table_contract(
            bind,
            "work_item_components",
            (
                "id", "object_type", "object_id", "component_id", "relation_type",
                "component_name_snapshot", "create_time",
            ),
            (
                ("object_type",), ("object_id",), ("component_id",), ("relation_type",),
            ),
            (("object_type", "object_id", "component_id"),),
            (("component_id", "business_components"),),
        )
    else:
        op.create_table(
        "work_item_components",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("object_type", sa.String(length=32), nullable=False),
        sa.Column("object_id", sa.BigInteger(), nullable=False),
        sa.Column("component_id", sa.BigInteger(), nullable=False),
        sa.Column("relation_type", sa.String(length=16), nullable=False),
        sa.Column("component_name_snapshot", sa.String(length=150), nullable=False),
        sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["component_id"], ["business_components.id"], name="fk_work_item_components_component", ondelete="RESTRICT"),
        sa.UniqueConstraint("object_type", "object_id", "component_id", name="uk_work_item_component"),
        )
        op.create_index("ix_work_item_components_object_type", "work_item_components", ["object_type"])
        op.create_index("ix_work_item_components_object_id", "work_item_components", ["object_id"])
        op.create_index("ix_work_item_components_component_id", "work_item_components", ["component_id"])
        op.create_index("ix_work_item_components_relation_type", "work_item_components", ["relation_type"])

    if "workflow_migration_logs" in existing_tables:
        _assert_existing_table_contract(
            bind,
            "workflow_migration_logs",
            (
                "id", "object_type", "object_id", "old_definition_id", "old_state_id",
                "new_definition_id", "new_state_id", "reason", "actor_id", "create_time",
            ),
            (("object_type",), ("object_id",)),
            (),
            (
                ("old_definition_id", "workflow_definitions"), ("old_state_id", "workflow_states"),
                ("new_definition_id", "workflow_definitions"), ("new_state_id", "workflow_states"),
                ("actor_id", "users"),
            ),
        )
    else:
        op.create_table(
        "workflow_migration_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("object_type", sa.String(length=32), nullable=False),
        sa.Column("object_id", sa.BigInteger(), nullable=False),
        sa.Column("old_definition_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("old_state_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("new_definition_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("new_state_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.BigInteger(), nullable=True),
        sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["old_definition_id"], ["workflow_definitions.id"], name="fk_workflow_migrations_old_definition", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["old_state_id"], ["workflow_states.id"], name="fk_workflow_migrations_old_state", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["new_definition_id"], ["workflow_definitions.id"], name="fk_workflow_migrations_new_definition", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["new_state_id"], ["workflow_states.id"], name="fk_workflow_migrations_new_state", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], name="fk_workflow_migrations_actor", ondelete="RESTRICT"),
        )
        op.create_index("ix_workflow_migration_logs_object_type", "workflow_migration_logs", ["object_type"])
        op.create_index("ix_workflow_migration_logs_object_id", "workflow_migration_logs", ["object_id"])


def downgrade() -> None:
    op.drop_table("workflow_migration_logs")
    op.drop_table("work_item_components")
    op.drop_table("business_component_transition_routes")
    op.drop_table("business_component_members")
    op.drop_table("business_components")
