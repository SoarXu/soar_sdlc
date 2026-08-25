"""remove Bug unassigned ownership actions

Revision ID: 20260824_004
Revises: 20260824_003
Create Date: 2026-08-25 09:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260824_004"
down_revision = "20260824_003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    transition_ids = bind.execute(
        sa.text(
            """
            SELECT transition.id
            FROM workflow_transitions AS transition
            JOIN workflow_states AS state
              ON state.id = transition.from_state_id
             AND state.definition_id = transition.definition_id
            JOIN workflow_definitions AS definition
              ON definition.id = transition.definition_id
            WHERE definition.object_type = 'bug'
              AND state.state_role = 'unassigned'
              AND transition.action_key IN ('transfer', 'change_handler')
            """
        )
    ).scalars().all()
    bind.execute(
        sa.text(
            "DELETE FROM workflow_transition_roles "
            "WHERE NOT EXISTS ("
            "SELECT 1 FROM workflow_transitions "
            "WHERE workflow_transitions.id = workflow_transition_roles.transition_id"
            ")"
        )
    )
    if not transition_ids:
        return

    deletion_params = sa.text(
        "DELETE FROM business_component_transition_routes WHERE transition_id IN :transition_ids"
    ).bindparams(
        sa.bindparam("transition_ids", expanding=True),
        transition_ids=transition_ids,
    )
    bind.execute(deletion_params)

    deletion_params = sa.text(
        "DELETE FROM workflow_transition_roles WHERE transition_id IN :transition_ids"
    ).bindparams(
        sa.bindparam("transition_ids", expanding=True),
        transition_ids=transition_ids,
    )
    bind.execute(deletion_params)

    bind.execute(
        sa.text("DELETE FROM workflow_transitions WHERE id IN :transition_ids").bindparams(
            sa.bindparam("transition_ids", expanding=True),
            transition_ids=transition_ids,
        )
    )


def downgrade() -> None:
    # Deleted transitions cannot be reconstructed without overriding the workflow author's configuration.
    pass
