"""project team role metadata

Revision ID: 20260624_003
Revises: 20260624_002
Create Date: 2026-06-24 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260624_003"
down_revision: Union[str, None] = "20260624_002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "project_members",
        sa.Column("is_default_assignee", sa.Boolean(), nullable=False, server_default=sa.text("0"), comment="是否默认分配人"),
    )
    op.add_column(
        "project_members",
        sa.Column("is_workbench_participant", sa.Boolean(), nullable=False, server_default=sa.text("1"), comment="是否进入工作台范围"),
    )
    op.add_column(
        "project_members",
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0"), comment="排序"),
    )


def downgrade() -> None:
    op.drop_column("project_members", "sort_order")
    op.drop_column("project_members", "is_workbench_participant")
    op.drop_column("project_members", "is_default_assignee")
