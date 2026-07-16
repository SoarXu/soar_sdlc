"""remove legacy status columns from core workflow items

Revision ID: 20260716_002
Revises: 20260716_001
Create Date: 2026-07-16 20:15:00.000000
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "20260716_002"
down_revision: Union[str, None] = "20260716_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _legacy_core_columns() -> dict[str, str]:
    return {"requirements": "status", "tasks": "status", "bugs": "status"}


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _invalid_reference_count(table_name: str) -> int:
    return int(
        op.get_bind().execute(
            sa.text(
                f"SELECT COUNT(*) FROM {table_name} item "
                "LEFT JOIN workflow_definitions definition ON definition.id = item.workflow_definition_id "
                "LEFT JOIN workflow_states state ON state.id = item.current_state_id "
                "WHERE item.workflow_definition_id IS NULL OR item.current_state_id IS NULL "
                "OR definition.id IS NULL OR state.id IS NULL "
                "OR state.definition_id <> item.workflow_definition_id"
            )
        ).scalar_one()
    )


def upgrade() -> None:
    for table_name in _legacy_core_columns():
        invalid_count = _invalid_reference_count(table_name)
        if invalid_count:
            raise RuntimeError(
                f"Cannot remove {table_name}.status: {invalid_count} rows have invalid workflow references"
            )

    bigint = mysql.BIGINT(unsigned=True)
    for table_name, column_name in _legacy_core_columns().items():
        op.alter_column(table_name, "workflow_definition_id", existing_type=bigint, nullable=False)
        op.alter_column(table_name, "current_state_id", existing_type=bigint, nullable=False)
        if column_name in _columns(table_name):
            op.drop_column(table_name, column_name)


def downgrade() -> None:
    defaults = {
        "requirements": "pending_assignment",
        "tasks": "pending_assignment",
        "bugs": "pending_handling",
    }
    bigint = mysql.BIGINT(unsigned=True)
    for table_name, column_name in _legacy_core_columns().items():
        if column_name not in _columns(table_name):
            op.add_column(
                table_name,
                sa.Column(column_name, sa.String(length=32), nullable=True),
            )
        op.execute(
            sa.text(
                f"UPDATE {table_name} item "
                "JOIN workflow_states state ON state.id = item.current_state_id "
                f"SET item.{column_name} = state.status_key"
            )
        )
        op.alter_column(
            table_name,
            column_name,
            existing_type=sa.String(length=32),
            nullable=False,
            server_default=defaults[table_name],
        )
        op.alter_column(table_name, "current_state_id", existing_type=bigint, nullable=True)
        op.alter_column(table_name, "workflow_definition_id", existing_type=bigint, nullable=True)
