"""add terminal iteration completion snapshots

Revision ID: 20260722_001
Revises: 20260720_003
Create Date: 2026-07-22 15:05:00.000000
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "20260722_001"
down_revision: Union[str, None] = "20260720_003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if "iteration_completion_snapshots" in sa.inspect(op.get_bind()).get_table_names():
        return
    bigint = mysql.BIGINT(unsigned=True)
    op.create_table(
        "iteration_completion_snapshots",
        sa.Column("id", bigint, primary_key=True, autoincrement=True),
        sa.Column("iteration_id", bigint, nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=False),
        sa.Column("actor_id", bigint, nullable=True),
        sa.Column("operation_log_id", bigint, nullable=False),
        sa.Column("iteration_snapshot", sa.JSON(), nullable=False),
        sa.Column("counts", sa.JSON(), nullable=False),
        sa.Column("terminal_counts", sa.JSON(), nullable=False),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("gate_result", sa.JSON(), nullable=False),
        sa.Column("create_time", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["iteration_id"], ["iterations.id"], name="fk_iteration_completion_snapshot_iteration", ondelete="CASCADE"),
        sa.UniqueConstraint("iteration_id", name="uk_iteration_completion_snapshot_iteration"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_comment="terminal iteration immutable snapshot",
    )


def downgrade() -> None:
    if "iteration_completion_snapshots" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("iteration_completion_snapshots")
