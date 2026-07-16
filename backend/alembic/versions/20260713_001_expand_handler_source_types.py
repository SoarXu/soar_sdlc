"""expand handler source type columns

Revision ID: 20260713_001
Revises: 20260710_002
Create Date: 2026-07-13 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260713_001"
down_revision: Union[str, None] = "20260710_002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "handler_transition_rules",
        "target_type",
        existing_type=sa.String(length=32),
        type_=sa.String(length=64),
        existing_nullable=False,
        existing_server_default="keep_current",
    )
    op.alter_column(
        "handler_transition_rules",
        "fallback_type",
        existing_type=sa.String(length=32),
        type_=sa.String(length=64),
        existing_nullable=False,
        existing_server_default="keep_current",
    )


def downgrade() -> None:
    op.alter_column(
        "handler_transition_rules",
        "fallback_type",
        existing_type=sa.String(length=64),
        type_=sa.String(length=32),
        existing_nullable=False,
        existing_server_default="keep_current",
    )
    op.alter_column(
        "handler_transition_rules",
        "target_type",
        existing_type=sa.String(length=64),
        type_=sa.String(length=32),
        existing_nullable=False,
        existing_server_default="keep_current",
    )
