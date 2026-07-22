"""disable duplicate debug Bug workflow definition

Revision ID: 20260723_001
Revises: 20260722_003
Create Date: 2026-07-23 10:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260723_001"
down_revision: Union[str, None] = "20260722_003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    debug_definition = bind.execute(
        sa.text(
            "SELECT id, scope_id FROM workflow_definitions "
            "WHERE id = 466 AND name = 'debug-def' AND object_type = 'bug' "
            "AND scope_type = 'assignee_rule_config' AND enabled = 1"
        )
    ).mappings().one_or_none()
    if not debug_definition:
        return
    default_definition = bind.execute(
        sa.text(
            "SELECT id FROM workflow_definitions "
            "WHERE id = 33 AND object_type = 'bug' AND scope_type = 'assignee_rule_config' "
            "AND scope_id = :scope_id AND enabled = 1"
        ),
        {"scope_id": debug_definition["scope_id"]},
    ).one_or_none()
    if default_definition:
        bind.execute(sa.text("UPDATE workflow_definitions SET enabled = 0 WHERE id = 466"))


def downgrade() -> None:
    # This migration repairs an invalid duplicate; it must not reintroduce it.
    pass
