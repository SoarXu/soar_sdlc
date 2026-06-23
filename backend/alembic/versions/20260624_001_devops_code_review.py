"""Add DevOps code review tables.

Revision ID: 20260624_001
Revises: 20260623_001
Create Date: 2026-06-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20260624_001"
down_revision = "20260623_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    if "devops_repositories" in existing_tables:
        return

    op.create_table(
        "devops_repositories",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("provider", sa.String(length=32), nullable=False, server_default="gitlab"),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("repository_url", sa.String(length=1000), nullable=True),
        sa.Column("external_project_id", sa.String(length=128), nullable=True),
        sa.Column("default_branch", sa.String(length=128), nullable=True),
        sa.Column("access_token_encrypted", sa.String(length=1000), nullable=True),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("update_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deleted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("delete_time", sa.DateTime(), nullable=True),
    )
    op.create_index("idx_devops_repo_provider_project", "devops_repositories", ["provider", "external_project_id"])

    op.create_table(
        "devops_jenkins_jobs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("job_name", sa.String(length=150), nullable=False),
        sa.Column("jenkins_url", sa.String(length=1000), nullable=True),
        sa.Column("repository_id", sa.BigInteger(), nullable=True),
        sa.Column("branch_pattern", sa.String(length=255), nullable=True),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("update_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deleted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("delete_time", sa.DateTime(), nullable=True),
    )
    op.create_index("idx_devops_jenkins_repo", "devops_jenkins_jobs", ["repository_id"])

    op.create_table(
        "devops_commits",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("provider", sa.String(length=32), nullable=False, server_default="gitlab"),
        sa.Column("repository_id", sa.BigInteger(), nullable=True),
        sa.Column("external_project_id", sa.String(length=128), nullable=True),
        sa.Column("commit_sha", sa.String(length=128), nullable=False),
        sa.Column("short_sha", sa.String(length=32), nullable=True),
        sa.Column("branch_name", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("author_name", sa.String(length=150), nullable=True),
        sa.Column("author_email", sa.String(length=255), nullable=True),
        sa.Column("committed_at", sa.DateTime(), nullable=True),
        sa.Column("web_url", sa.String(length=1000), nullable=True),
        sa.Column("diff_text", mysql.MEDIUMTEXT(), nullable=True),
        sa.Column("diff_json", sa.JSON(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("review_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("reviewer_id", sa.BigInteger(), nullable=True),
        sa.Column("review_time", sa.DateTime(), nullable=True),
        sa.Column("review_remark", sa.Text(), nullable=True),
        sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("update_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deleted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("delete_time", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("provider", "repository_id", "commit_sha", name="uk_devops_commit_repo_sha"),
    )
    op.create_index("idx_devops_commit_sha", "devops_commits", ["commit_sha"])
    op.create_index("idx_devops_commit_status", "devops_commits", ["review_status"])

    op.create_table(
        "devops_commit_links",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("commit_id", sa.BigInteger(), nullable=False),
        sa.Column("object_type", sa.String(length=64), nullable=False),
        sa.Column("object_id", sa.BigInteger(), nullable=False),
        sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("commit_id", "object_type", "object_id", name="uk_devops_commit_link"),
    )
    op.create_index("idx_devops_commit_link_object", "devops_commit_links", ["object_type", "object_id"])

    op.create_table(
        "devops_code_review_tasks",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("commit_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("owner_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("update_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("finish_time", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("commit_id", name="uk_devops_review_commit"),
    )
    op.create_index("idx_devops_review_status", "devops_code_review_tasks", ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    for table_name in [
        "devops_code_review_tasks",
        "devops_commit_links",
        "devops_commits",
        "devops_jenkins_jobs",
        "devops_repositories",
    ]:
        if table_name in existing_tables:
            op.drop_table(table_name)
