"""move system administrator status to users

Revision ID: 20260819_002
Revises: 20260819_001
"""

from alembic import op
import sqlalchemy as sa


revision = "20260819_002"
down_revision = "20260819_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_system_admin", sa.Boolean(), nullable=False, server_default=sa.text("0")))
    op.execute(
        "UPDATE users SET is_system_admin = 1 WHERE id IN "
        "(SELECT user_roles.user_id FROM user_roles JOIN roles ON roles.id = user_roles.role_id "
        "WHERE roles.role_key = 'system_admin')"
    )
    op.execute("DELETE FROM user_roles WHERE role_id IN (SELECT id FROM roles WHERE role_key = 'system_admin')")
    op.execute("DELETE FROM roles WHERE role_key = 'system_admin'")


def downgrade() -> None:
    op.drop_column("users", "is_system_admin")
