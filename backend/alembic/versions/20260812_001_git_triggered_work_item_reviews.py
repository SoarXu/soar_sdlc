"""add work-item review rounds for Git-triggered review

Revision ID: 20260812_001
Revises: 20260811_002
Create Date: 2026-08-12 17:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260812_001"
down_revision: Union[str, None] = "20260811_002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if "work_item_review_rounds" in sa.inspect(bind).get_table_names():
        return
    op.create_table(
        "work_item_review_rounds",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("object_type", sa.String(length=32), nullable=False),
        sa.Column("object_id", sa.BigInteger(), nullable=False),
        sa.Column("latest_commit_id", sa.BigInteger(), nullable=False),
        sa.Column("reviewer_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("active_key", sa.String(length=16), nullable=True),
        sa.Column("decision_by_id", sa.BigInteger(), nullable=True),
        sa.Column("decision_at", sa.DateTime(), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("update_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("object_type", "object_id", "active_key", name="uk_work_item_review_round_active"),
    )
    op.create_index(
        "ix_work_item_review_round_reviewer_status",
        "work_item_review_rounds",
        ["reviewer_id", "status"],
    )
    op.create_index(
        "ix_work_item_review_round_object_status",
        "work_item_review_rounds",
        ["object_type", "object_id", "status"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if "work_item_review_rounds" in sa.inspect(bind).get_table_names():
        op.drop_table("work_item_review_rounds")
