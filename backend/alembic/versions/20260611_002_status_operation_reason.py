"""Add reason to status operation logs.

Revision ID: 20260611_002
Revises: 20260611_001
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa


revision = "20260611_002"
down_revision = "20260611_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("status_operation_log", sa.Column("reason", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("status_operation_log", "reason")
