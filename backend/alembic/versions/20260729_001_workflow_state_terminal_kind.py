"""add workflow state terminal outcome

Revision ID: 20260729_001
Revises: 20260728_001
Create Date: 2026-07-29 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260729_001"
down_revision: Union[str, None] = "20260728_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("workflow_states", sa.Column("terminal_kind", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("workflow_states", "terminal_kind")
