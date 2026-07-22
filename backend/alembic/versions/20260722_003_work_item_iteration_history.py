"""ensure work item iteration history table

Revision ID: 20260722_003
Revises: 20260722_002
Create Date: 2026-07-22 18:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "20260722_003"
down_revision: Union[str, None] = "20260722_002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns() -> list[sa.Column]:
    bigint = mysql.BIGINT(unsigned=True)
    return [
        sa.Column("id", bigint, primary_key=True, autoincrement=True),
        sa.Column("object_type", sa.String(32), nullable=False),
        sa.Column("object_id", bigint, nullable=False),
        sa.Column("iteration_id", bigint, nullable=False),
        sa.Column("entered_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("entered_by", bigint, nullable=True),
        sa.Column("enter_reason", sa.String(64), nullable=False),
        sa.Column("left_at", sa.DateTime(), nullable=True),
        sa.Column("left_by", bigint, nullable=True),
        sa.Column("leave_reason", sa.String(64), nullable=True),
        sa.Column("title_snapshot", sa.String(255), nullable=True),
        sa.Column("state_id_snapshot", bigint, nullable=True),
        sa.Column("status_name_snapshot", sa.String(100), nullable=True),
        sa.Column("owner_id_snapshot", bigint, nullable=True),
        sa.Column("operation_log_id", bigint, nullable=True),
        sa.Column("migrated", sa.Integer(), nullable=False, server_default="0"),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "work_item_iteration_history" not in inspector.get_table_names():
        op.create_table("work_item_iteration_history", *_columns(), mysql_engine="InnoDB", mysql_charset="utf8mb4")
        op.create_index("idx_wiih_object", "work_item_iteration_history", ["object_type", "object_id", "left_at"])
        op.create_index("idx_wiih_iteration", "work_item_iteration_history", ["iteration_id", "left_at"])
        return

    existing_columns = {column["name"] for column in inspector.get_columns("work_item_iteration_history")}
    for column in _columns():
        if column.name != "id" and column.name not in existing_columns:
            op.add_column("work_item_iteration_history", column.copy())
    indexes = sa.inspect(bind).get_indexes("work_item_iteration_history")
    canonical = next((index for index in indexes if index.get("name") == "idx_wiih_object"), None)
    if canonical and canonical.get("column_names") != ["object_type", "object_id", "left_at"]:
        op.drop_index("idx_wiih_object", table_name="work_item_iteration_history")
        canonical = None
    if not canonical and not any(
        index.get("column_names") == ["object_type", "object_id", "left_at"] for index in indexes
    ):
        op.create_index("idx_wiih_object", "work_item_iteration_history", ["object_type", "object_id", "left_at"])
    if not any(index.get("column_names") == ["iteration_id", "left_at"] for index in indexes):
        op.create_index("idx_wiih_iteration", "work_item_iteration_history", ["iteration_id", "left_at"])


def downgrade() -> None:
    if "work_item_iteration_history" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("work_item_iteration_history")
