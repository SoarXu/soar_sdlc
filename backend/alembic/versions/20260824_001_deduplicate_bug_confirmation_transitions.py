"""deduplicate managed Bug confirmation transitions

Revision ID: 20260824_001
Revises: 20260822_006
Create Date: 2026-08-24 14:00:00.000000
"""

from alembic import op
from sqlalchemy.orm import Session

from app.services.default_workflow_template_service import reconcile_managed_bug_action_matrices


revision = "20260824_001"
down_revision = "20260822_006"
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
    # Do not re-enable historical duplicate actions.
    pass
