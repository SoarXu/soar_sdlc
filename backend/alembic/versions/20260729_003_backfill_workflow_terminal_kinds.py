"""backfill canonical terminal outcomes for enabled workflows

Revision ID: 20260729_003
Revises: 20260729_002
Create Date: 2026-07-29 13:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260729_003"
down_revision: Union[str, None] = "20260729_002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _backfill_terminal_kind_statement(dialect_name: str = "sqlite"):
    case_expression = """
        CASE status_name
            WHEN '已完成' THEN 'completed'
            WHEN '已关闭' THEN 'completed'
            WHEN '已取消' THEN 'terminated'
            WHEN '已挂起' THEN 'terminated'
        END
    """
    if dialect_name == "sqlite":
        return sa.text(f"""
            UPDATE workflow_states
            SET terminal_kind = {case_expression}
            WHERE terminal_kind IS NULL
              AND category = 'terminal'
              AND status_name IN ('已完成', '已关闭', '已取消', '已挂起')
              AND definition_id IN (
                  SELECT id FROM workflow_definitions WHERE enabled = 1
              )
        """)
    if dialect_name in {"mysql", "mariadb"}:
        return sa.text(f"""
            UPDATE workflow_states
            JOIN workflow_definitions
              ON workflow_definitions.id = workflow_states.definition_id
            SET workflow_states.terminal_kind = {case_expression}
            WHERE workflow_states.terminal_kind IS NULL
              AND workflow_states.category = 'terminal'
              AND workflow_states.status_name IN ('已完成', '已关闭', '已取消', '已挂起')
              AND workflow_definitions.enabled = 1
        """)
    raise RuntimeError(f"Unsupported database dialect: {dialect_name}")


def upgrade() -> None:
    op.execute(_backfill_terminal_kind_statement(op.get_bind().dialect.name))


def downgrade() -> None:
    # Backfilled values are indistinguishable from values configured by users.
    pass
