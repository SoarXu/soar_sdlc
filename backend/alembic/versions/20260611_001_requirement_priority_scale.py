"""Convert requirement priority to 1-5 scale.

Revision ID: 20260611_001
Revises: None
Create Date: 2026-06-11
"""
from alembic import op


revision = "20260611_001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE requirements ALTER COLUMN priority SET DEFAULT '3'")
    op.execute("UPDATE requirements SET priority = '1' WHERE priority = 'high'")
    op.execute("UPDATE requirements SET priority = '3' WHERE priority = 'medium'")
    op.execute("UPDATE requirements SET priority = '5' WHERE priority = 'low'")


def downgrade() -> None:
    op.execute("ALTER TABLE requirements ALTER COLUMN priority SET DEFAULT 'medium'")
    op.execute("UPDATE requirements SET priority = 'high' WHERE priority = '1'")
    op.execute("UPDATE requirements SET priority = 'medium' WHERE priority = '3'")
    op.execute("UPDATE requirements SET priority = 'low' WHERE priority = '5'")
