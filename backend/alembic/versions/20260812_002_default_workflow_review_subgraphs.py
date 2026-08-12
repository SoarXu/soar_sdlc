"""install review subgraphs in default workflows

Revision ID: 20260812_002
Revises: 20260812_001
Create Date: 2026-08-12 17:15:00.000000
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
from sqlalchemy.orm import Session

from app.models.assignee_rule_config import AssigneeRuleConfig
from app.models.workflow_definition import WorkflowDefinition
from app.services.assignee_rule_config_service import DEFAULT_ASSIGNEE_RULE_CONFIG
from app.services.default_workflow_template_service import reconcile_review_subgraph


revision: str = "20260812_002"
down_revision: Union[str, None] = "20260812_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    session = Session(bind=op.get_bind())
    try:
        default_config_id = session.query(AssigneeRuleConfig.id).filter(
            AssigneeRuleConfig.name == DEFAULT_ASSIGNEE_RULE_CONFIG["name"]
        ).scalar()
        definitions = session.query(WorkflowDefinition).filter(
            WorkflowDefinition.object_type.in_(("requirement", "task", "bug")),
            (
                (WorkflowDefinition.scope_type == "system")
                | (
                    (WorkflowDefinition.scope_type == "assignee_rule_config")
                    & (WorkflowDefinition.scope_id == default_config_id)
                )
            ),
        ).all()
        for definition in definitions:
            reconcile_review_subgraph(session, definition)
        session.flush()
    finally:
        session.close()


def downgrade() -> None:
    # Existing graphs may have been explicitly extended by administrators; retain review history and graph nodes.
    pass
