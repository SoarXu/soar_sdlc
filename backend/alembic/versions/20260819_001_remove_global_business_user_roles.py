"""remove global business user roles

Revision ID: 20260819_001
Revises: 20260818_002
Create Date: 2026-08-19 12:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260819_001"
down_revision: Union[str, None] = "20260818_002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    user_roles = sa.table("user_roles", sa.column("role_id"))
    roles = sa.table("roles", sa.column("id"), sa.column("role_key"))
    op.execute(
        user_roles.delete().where(
            user_roles.c.role_id.in_(
                sa.select(roles.c.id).where(roles.c.role_key != "system_admin")
            )
        )
    )


def downgrade() -> None:
    # Removed global business-role bindings cannot be reconstructed safely.
    pass
