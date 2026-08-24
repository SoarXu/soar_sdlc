"""add task descendant terminal transition gate

Revision ID: 20260822_006
Revises: 20260822_005
Create Date: 2026-08-24 11:00:00.000000
"""

from alembic import op
from sqlalchemy.orm import Session

from app.services.default_workflow_template_service import reconcile_managed_task_terminal_gates


revision = "20260822_006"
down_revision = "20260822_005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    session = Session(bind=op.get_bind())
    try:
        reconcile_managed_task_terminal_gates(session)
        session.commit()
    finally:
        session.close()


def downgrade() -> None:
    return None
