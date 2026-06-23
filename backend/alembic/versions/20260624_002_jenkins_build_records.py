"""Add Jenkins build records.

Revision ID: 20260624_002
Revises: 20260624_001
Create Date: 2026-06-24
"""
from alembic import op
import sqlalchemy as sa


revision = "20260624_002"
down_revision = "20260624_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "devops_jenkins_builds" in inspector.get_table_names():
        return
    op.create_table(
        "devops_jenkins_builds",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("job_id", sa.BigInteger(), nullable=True),
        sa.Column("job_name", sa.String(length=150), nullable=False),
        sa.Column("build_number", sa.String(length=64), nullable=False),
        sa.Column("build_url", sa.String(length=1000), nullable=True),
        sa.Column("branch_name", sa.String(length=255), nullable=True),
        sa.Column("commit_sha", sa.String(length=128), nullable=True),
        sa.Column("commit_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="running"),
        sa.Column("trigger_user", sa.String(length=150), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("update_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("job_id", "build_number", name="uk_devops_jenkins_build"),
    )
    op.create_index("idx_devops_jenkins_build_job", "devops_jenkins_builds", ["job_id"])
    op.create_index("idx_devops_jenkins_build_commit", "devops_jenkins_builds", ["commit_sha"])
    op.create_index("idx_devops_jenkins_build_status", "devops_jenkins_builds", ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "devops_jenkins_builds" in inspector.get_table_names():
        op.drop_table("devops_jenkins_builds")
