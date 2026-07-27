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


def upgrade() -> None:
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
