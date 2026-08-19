"""add workflow transition role references

Revision ID: 20260819_004
Revises: 20260819_003
"""

from alembic import op
import json
import sqlalchemy as sa
from sqlalchemy.orm import Session

revision = "20260819_004"
down_revision = "20260819_003"
branch_labels = None
depends_on = None


ROLE_ALIASES = {"product_owner": "product_manager", "tech_lead": "development_lead", "test_lead": "tester"}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "workflow_transition_roles" not in inspector.get_table_names():
        op.create_table(
            "workflow_transition_roles",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("transition_id", sa.BigInteger(), nullable=False),
            sa.Column("role_id", sa.BigInteger(), nullable=False),
            sa.Column("purpose", sa.String(length=32), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        )
        op.create_index("ix_workflow_transition_roles_transition_id", "workflow_transition_roles", ["transition_id"])
        op.create_index("ix_workflow_transition_roles_role_id", "workflow_transition_roles", ["role_id"])
    session = Session(bind=op.get_bind())
    try:
        role_ids = dict(session.execute(sa.text("SELECT role_key, id FROM roles")).all())
        transitions = session.execute(sa.text("SELECT id, allowed_roles, handler_rule FROM workflow_transitions")).all()
        references = []
        for transition_id, allowed_roles, handler_rule in transitions:
            rule = handler_rule if isinstance(handler_rule, dict) else json.loads(handler_rule or "{}")
            for purpose, values in (
                ("allowed", allowed_roles),
                ("target", rule.get("target_roles")),
                ("fallback", rule.get("fallback_roles")),
            ):
                for index, role_key in enumerate((values or "").split(",")):
                    normalized_role_key = ROLE_ALIASES.get(role_key.strip(), role_key.strip())
                    role_id = role_ids.get(normalized_role_key)
                    if role_id:
                        references.append({"transition_id": transition_id, "role_id": role_id, "purpose": purpose, "sort_order": index})
        if references:
            op.bulk_insert(sa.table("workflow_transition_roles", sa.column("transition_id"), sa.column("role_id"), sa.column("purpose"), sa.column("sort_order")), references)
    finally:
        session.close()


def downgrade() -> None:
    op.drop_table("workflow_transition_roles")
