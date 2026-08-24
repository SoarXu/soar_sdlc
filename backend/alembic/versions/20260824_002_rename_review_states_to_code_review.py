"""rename review states to Code Review

Revision ID: 20260824_002
Revises: 20260824_001
Create Date: 2026-08-24 16:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260824_002"
down_revision = "20260824_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    _rename_review_states("待评审", "Code Review")


def downgrade() -> None:
    # A display-name migration cannot distinguish rows changed by upgrade from
    # pre-existing custom Code Review states, so rollback must not rewrite data.
    pass


def _rename_review_states(old_status_name: str, new_status_name: str) -> None:
    op.execute(
        sa.text(
            """
            UPDATE workflow_states
            SET status_name = :new_status_name
            WHERE status_name = :old_status_name
              AND definition_id IN (
                  SELECT id
                  FROM workflow_definitions
                  WHERE object_type IN ('requirement', 'task', 'bug')
              )
            """
        ).bindparams(
            old_status_name=old_status_name,
            new_status_name=new_status_name,
        )
    )
