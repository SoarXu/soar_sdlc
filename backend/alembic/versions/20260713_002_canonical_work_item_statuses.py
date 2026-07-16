"""migrate work items to canonical statuses

Revision ID: 20260713_002
Revises: 20260713_001
Create Date: 2026-07-13 14:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260713_002"
down_revision: Union[str, None] = "20260713_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("""
        UPDATE requirements
        SET status = CASE
            WHEN status = 'draft' THEN CASE WHEN owner_id IS NULL THEN 'pending_assignment' ELSE 'in_processing' END
            WHEN status IN ('active', 'validation_failed') THEN 'in_processing'
            WHEN status = 'pending_validation' THEN 'pending_confirmation'
            WHEN status = 'done' THEN 'completed'
            WHEN status = 'closed' THEN 'canceled'
            ELSE status
        END
        WHERE status IN ('draft', 'active', 'validation_failed', 'pending_validation', 'done', 'closed')
    """))
    op.execute(sa.text("""
        UPDATE tasks
        SET status = CASE
            WHEN status = 'todo' THEN CASE WHEN owner_id IS NULL THEN 'pending_assignment' ELSE 'in_processing' END
            WHEN status = 'doing' THEN 'in_processing'
            WHEN status = 'done' THEN 'completed'
            WHEN status = 'closed' THEN 'canceled'
            ELSE status
        END
        WHERE status IN ('todo', 'doing', 'done', 'closed')
    """))
    op.execute(sa.text("""
        UPDATE bugs
        SET status = CASE
            WHEN status IN ('open', 'reopened', 'suspended') THEN 'pending_handling'
            WHEN status = 'verifying' THEN 'pending_verification'
            ELSE status
        END
        WHERE status IN ('open', 'reopened', 'suspended', 'verifying')
    """))
    op.execute(sa.text("UPDATE iterations SET status = 'completed' WHERE status = 'finished'"))
    op.execute(sa.text("UPDATE iterations SET status = 'canceled' WHERE status = 'closed'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE requirements SET status = 'draft' WHERE status = 'pending_assignment'"))
    op.execute(sa.text("UPDATE requirements SET status = 'active' WHERE status = 'in_processing'"))
    op.execute(sa.text("UPDATE requirements SET status = 'pending_validation' WHERE status = 'pending_confirmation'"))
    op.execute(sa.text("UPDATE requirements SET status = 'done' WHERE status = 'completed'"))
    op.execute(sa.text("UPDATE requirements SET status = 'closed' WHERE status = 'canceled'"))
    op.execute(sa.text("UPDATE tasks SET status = 'todo' WHERE status = 'pending_assignment'"))
    op.execute(sa.text("UPDATE tasks SET status = 'doing' WHERE status = 'in_processing'"))
    op.execute(sa.text("UPDATE tasks SET status = 'done' WHERE status = 'completed'"))
    op.execute(sa.text("UPDATE tasks SET status = 'closed' WHERE status = 'canceled'"))
    op.execute(sa.text("UPDATE bugs SET status = 'open' WHERE status = 'pending_handling'"))
    op.execute(sa.text("UPDATE bugs SET status = 'verifying' WHERE status = 'pending_verification'"))
    op.execute(sa.text("UPDATE iterations SET status = 'finished' WHERE status = 'completed'"))
    op.execute(sa.text("UPDATE iterations SET status = 'closed' WHERE status = 'canceled'"))
