"""Allow full custom workflow action keys in operation history.

Revision ID: 20261113_001
Revises: 20260910_003
"""
from alembic import context, op
import sqlalchemy as sa


revision = "20261113_001"
down_revision = "20260910_003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not context.is_offline_mode():
        column = next(
            column for column in sa.inspect(op.get_bind()).get_columns("status_operation_log")
            if column["name"] == "action"
        )
        if (getattr(column["type"], "length", None) or 0) >= 64:
            return
    op.alter_column(
        "status_operation_log", "action",
        existing_type=sa.String(32), type_=sa.String(64), existing_nullable=False,
    )


def downgrade() -> None:
    # Retain the larger capacity: shrinking can truncate valid custom action keys.
    pass
