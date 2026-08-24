"""rename work-item add-information actions to comment

Revision ID: 20260824_003
Revises: 20260824_002
Create Date: 2026-08-24 17:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260824_003"
down_revision = "20260824_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    transition_ids = bind.execute(
        sa.text(
            """
            SELECT transition.id
            FROM workflow_transitions AS transition
            WHERE transition.action_key = :action_key
              AND transition.action_name = :old_action_name
              AND transition.definition_id IN (
                  SELECT id
                  FROM workflow_definitions
                  WHERE object_type IN ('requirement', 'task', 'bug')
              )
              AND (
                  transition.enabled = 0
                  OR NOT EXISTS (
                      SELECT 1
                      FROM workflow_transitions AS existing
                      WHERE existing.definition_id = transition.definition_id
                        AND existing.from_state_id = transition.from_state_id
                        AND existing.action_name = :new_action_name
                        AND existing.enabled = 1
                        AND existing.id != transition.id
                  )
              )
            """
        ).bindparams(
            action_key="add_information",
            old_action_name="补充信息",
            new_action_name="评论",
        )
    ).scalars().all()
    if not transition_ids:
        return
    bind.execute(
        sa.text(
            "UPDATE workflow_transitions SET action_name = :new_action_name "
            "WHERE id IN :transition_ids"
        ).bindparams(
            sa.bindparam("transition_ids", expanding=True),
            new_action_name="评论",
            transition_ids=transition_ids,
        )
    )


def downgrade() -> None:
    # The previous value could have been deliberately customized to “评论”.
    # Preserve that user intent instead of performing a destructive rewrite.
    pass
