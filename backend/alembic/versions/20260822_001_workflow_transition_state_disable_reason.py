"""track transitions disabled by an unavailable state

Revision ID: 20260822_001
Revises: 20260819_008
Create Date: 2026-08-22 14:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision = "20260822_001"
down_revision = "20260819_008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if "auto_disabled_by_state" not in _column_names(bind, "workflow_transitions"):
        op.add_column(
            "workflow_transitions",
            sa.Column(
                "auto_disabled_by_state",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if "auto_disabled_by_state" in _column_names(bind, "workflow_transitions"):
        op.drop_column("workflow_transitions", "auto_disabled_by_state")


def _column_names(bind, table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table_name)}
