"""remove legacy business component member roles

Revision ID: 20260806_001
Revises: 20260803_002
Create Date: 2026-08-06 09:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260806_001"
down_revision: Union[str, None] = "20260803_002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Legacy component responsibilities (owner/handler/reviewer/approver) are
    # not backend roles and must not remain eligible for component workflows.
    op.get_bind().execute(
        sa.text(
            "DELETE FROM business_component_members "
            "WHERE NOT EXISTS ("
            "SELECT 1 FROM roles "
            "WHERE roles.role_key = business_component_members.component_role "
            "AND roles.enabled = 1"
            ")"
        )
    )


def downgrade() -> None:
    # Deleted legacy values cannot be reconstructed safely.
    pass
