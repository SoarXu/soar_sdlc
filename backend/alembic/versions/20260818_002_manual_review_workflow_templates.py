"""allow manual review submission in system workflow templates

Revision ID: 20260818_002
Revises: 20260818_001
Create Date: 2026-08-19 00:10:00.000000
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
from sqlalchemy.orm import Session

from app.models.workflow_definition import WorkflowDefinition, WorkflowTransition


revision: str = "20260818_002"
down_revision: Union[str, None] = "20260818_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    session = Session(bind=op.get_bind())
    try:
        definitions = session.query(WorkflowDefinition).filter(
            WorkflowDefinition.scope_type == "system",
            WorkflowDefinition.is_default_template.is_(True),
            WorkflowDefinition.template_key.in_(("requirement.default", "task.default", "bug.default")),
        ).all()
        definition_ids = [definition.id for definition in definitions]
        if definition_ids:
            for transition in session.query(WorkflowTransition).filter(
                WorkflowTransition.definition_id.in_(definition_ids),
                WorkflowTransition.action_key == "submit_review",
            ):
                transition.trigger_config = None
        session.flush()
    finally:
        session.close()


def downgrade() -> None:
    # Manual review submission is intentionally retained after downgrade.
    pass
