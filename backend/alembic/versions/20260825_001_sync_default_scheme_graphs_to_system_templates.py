"""sync default scheme graphs to system templates

Revision ID: 20260825_001
Revises: 20260824_004
Create Date: 2026-08-25 14:00:00.000000
"""

from alembic import op
from sqlalchemy.orm import Session

from app.services.assignee_rule_config_service import synchronize_default_scheme_graphs_to_system_templates


revision = "20260825_001"
down_revision = "20260824_004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    session = Session(bind=op.get_bind())
    try:
        synchronize_default_scheme_graphs_to_system_templates(session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def downgrade() -> None:
    # The previous system template graph is not recoverable after an intentional one-way synchronization.
    pass
