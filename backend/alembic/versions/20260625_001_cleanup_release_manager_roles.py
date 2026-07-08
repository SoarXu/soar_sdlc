"""cleanup release manager test roles

Revision ID: 20260625_001
Revises: 20260624_003
Create Date: 2026-06-25 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260625_001"
down_revision: Union[str, None] = "20260624_003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    role_ids = [
        row.id
        for row in connection.execute(
            sa.text(
                """
                select id
                from roles
                where is_system = 0
                  and (role_key = 'release_manager' or role_key like 'release_manager\\_%')
                """
            )
        )
    ]
    if not role_ids:
        return

    role_ids_param = sa.bindparam("role_ids", expanding=True)
    connection.execute(
        sa.text("delete from user_roles where role_id in :role_ids").bindparams(role_ids_param),
        {"role_ids": role_ids},
    )
    connection.execute(
        sa.text("delete from roles where id in :role_ids").bindparams(role_ids_param),
        {"role_ids": role_ids},
    )


def downgrade() -> None:
    pass
