"""add bug type dictionary

Revision ID: 20260710_001
Revises: 20260709_002
Create Date: 2026-07-10 10:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260710_001"
down_revision: Union[str, None] = "20260709_002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_ROWS = [
    ("code_issue", "代码问题", True, "fixing", 10),
    ("configuration_issue", "配置问题", True, "fixing", 20),
    ("data_issue", "数据问题", True, "fixing", 30),
    ("environment_issue", "环境问题", None, "pending_verification", 40),
    ("requirement_issue", "需求问题", None, "pending_verification", 50),
    ("design_as_intended", "设计如此", False, "pending_verification", 60),
    ("duplicate_issue", "重复问题", False, "pending_verification", 70),
    ("cannot_reproduce", "无法复现", False, "pending_verification", 80),
    ("operation_issue", "操作问题", False, "pending_verification", 90),
]


def upgrade() -> None:
    table = op.create_table(
        "bug_types",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("type_key", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("is_real_bug", sa.Boolean(), nullable=True),
        sa.Column("default_target_status", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("update_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("type_key", name="uq_bug_types_type_key"),
    )
    op.create_index("ix_bug_types_type_key", "bug_types", ["type_key"])
    op.bulk_insert(
        table,
        [
            {
                "type_key": key,
                "display_name": name,
                "is_real_bug": is_real,
                "default_target_status": target,
                "enabled": True,
                "sort_order": order,
            }
            for key, name, is_real, target, order in DEFAULT_ROWS
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_bug_types_type_key", table_name="bug_types")
    op.drop_table("bug_types")
