"""map repositories to Git platform connections

Revision ID: 20260817_003
Revises: 20260817_002
Create Date: 2026-08-17 19:00:00.000000
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260817_003"
down_revision: Union[str, None] = "20260817_002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "devops_repositories" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("devops_repositories")}
    if "git_platform_connection_id" not in columns:
        op.add_column("devops_repositories", sa.Column("git_platform_connection_id", sa.BigInteger(), nullable=True))
    indexes = {item["name"] for item in sa.inspect(bind).get_indexes("devops_repositories")}
    if "ix_devops_repository_git_platform_connection" not in indexes:
        op.create_index("ix_devops_repository_git_platform_connection", "devops_repositories", ["git_platform_connection_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "devops_repositories" not in inspector.get_table_names():
        return
    indexes = {item["name"] for item in inspector.get_indexes("devops_repositories")}
    if "ix_devops_repository_git_platform_connection" in indexes:
        op.drop_index("ix_devops_repository_git_platform_connection", table_name="devops_repositories")
    columns = {column["name"] for column in sa.inspect(bind).get_columns("devops_repositories")}
    if "git_platform_connection_id" in columns:
        op.drop_column("devops_repositories", "git_platform_connection_id")
