"""add project member role ID

Revision ID: 20260819_003
Revises: 20260819_002
"""

from alembic import op
import sqlalchemy as sa

revision = "20260819_003"
down_revision = "20260819_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("project_members", sa.Column("role_id", sa.BigInteger(), nullable=True))
    op.execute(
        "UPDATE project_members JOIN roles ON roles.role_key = project_members.project_role "
        "SET project_members.role_id = roles.id"
    )
    op.create_index("ix_project_members_role_id", "project_members", ["role_id"])


def downgrade() -> None:
    op.drop_index("ix_project_members_role_id", table_name="project_members")
    op.drop_column("project_members", "role_id")
