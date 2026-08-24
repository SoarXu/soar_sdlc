"""align managed Bug confirmation with the active-work state

Revision ID: 20260822_004
Revises: 20260822_003
Create Date: 2026-08-22 18:00:00.000000
"""

from alembic import op
from sqlalchemy.orm import Session

from app.services.default_workflow_template_service import reconcile_managed_bug_action_matrices


revision = "20260822_004"
down_revision = "20260822_003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    session = Session(bind=op.get_bind())
    try:
        reconcile_managed_bug_action_matrices(session)
        session.commit()
    finally:
        session.close()


def downgrade() -> None:
    # Do not restore an unreachable unassigned confirmation action.
    pass
