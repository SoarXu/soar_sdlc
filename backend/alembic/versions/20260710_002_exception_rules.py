"""add configurable exception rules

Revision ID: 20260710_002
Revises: 20260710_001
Create Date: 2026-07-10 16:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260710_002"
down_revision: Union[str, None] = "20260710_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_ROWS = [
    ("unassigned_timeout", "未分派超时", "*", 24, None, 10),
    ("pending_timeout", "待处理超时", "*", 24, None, 20),
    ("fixing_timeout", "修复/处理超时", "bug", 24, None, 30),
    ("fixing_timeout", "修复/处理超时", "task", 24, None, 31),
    ("pending_verification_timeout", "待验证超时", "bug", 24, None, 40),
    ("verified_not_closed", "已验证未关闭", "bug", 24, None, 50),
    ("verification_failed", "验证失败", "bug", 0, None, 60),
    ("repeated_activation", "重复激活", "bug", None, 2, 70),
    ("high_priority_unprocessed", "高优先级未处理", "*", 4, None, 80),
    ("completed_requirement_active_bug", "已完成需求存在活动 Bug", "requirement", 0, None, 90),
]


def upgrade() -> None:
    table = op.create_table(
        "exception_rules",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("exception_key", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("object_type", sa.String(length=64), nullable=False, server_default="*"),
        sa.Column("project_id", sa.BigInteger(), nullable=True),
        sa.Column("priority", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("threshold_hours", sa.Integer(), nullable=True),
        sa.Column("threshold_count", sa.Integer(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("creator_id", sa.BigInteger(), nullable=True),
        sa.Column("updater_id", sa.BigInteger(), nullable=True),
        sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("update_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_exception_rules_exception_key", "exception_rules", ["exception_key"])
    op.create_index("ix_exception_rules_project_id", "exception_rules", ["project_id"])
    op.bulk_insert(
        table,
        [
            {
                "exception_key": key,
                "label": label,
                "object_type": object_type,
                "threshold_hours": hours,
                "threshold_count": count,
                "enabled": True,
                "sort_order": order,
            }
            for key, label, object_type, hours, count, order in DEFAULT_ROWS
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_exception_rules_project_id", table_name="exception_rules")
    op.drop_index("ix_exception_rules_exception_key", table_name="exception_rules")
    op.drop_table("exception_rules")
