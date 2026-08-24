"""add stable roles for work-item workflow states

Revision ID: 20260822_002
Revises: 20260822_001
Create Date: 2026-08-22 15:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260822_002"
down_revision = "20260822_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "state_role" not in _column_names(bind, "workflow_states"):
        op.add_column(
            "workflow_states",
            sa.Column("state_role", sa.String(length=32), nullable=True),
        )
    if "ix_workflow_states_definition_state_role" not in _index_names(bind, "workflow_states"):
        op.create_index(
            "ix_workflow_states_definition_state_role",
            "workflow_states",
            ["definition_id", "state_role"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if "ix_workflow_states_definition_state_role" in _index_names(bind, "workflow_states"):
        op.drop_index("ix_workflow_states_definition_state_role", table_name="workflow_states")
    if "state_role" in _column_names(bind, "workflow_states"):
        op.drop_column("workflow_states", "state_role")


def _column_names(bind, table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}


def _index_names(bind, table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}
