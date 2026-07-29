"""add Git platform connections

Revision ID: 20260729_004
Revises: 20260729_003
Create Date: 2026-07-29 16:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260729_004"
down_revision: Union[str, None] = "20260729_003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_name = "devops_git_platform_connections"
    if table_name not in inspector.get_table_names():
        op.create_table(
            table_name,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(length=150), nullable=False, unique=True),
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.Column("base_url", sa.String(length=1000), nullable=False),
            sa.Column("access_token_encrypted", sa.Text(), nullable=True),
            sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("authenticated_username", sa.String(length=255), nullable=True),
            sa.Column("connection_status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("last_verified_at", sa.DateTime(), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("update_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("deleted", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("delete_time", sa.DateTime(), nullable=True),
        )
        inspector = sa.inspect(bind)
    if not any(index["name"] == "ix_devops_git_platform_connections_deleted" for index in inspector.get_indexes(table_name)):
        op.create_index("ix_devops_git_platform_connections_deleted", table_name, ["deleted"])


def downgrade() -> None:
    op.drop_index("ix_devops_git_platform_connections_deleted", table_name="devops_git_platform_connections")
    op.drop_table("devops_git_platform_connections")
