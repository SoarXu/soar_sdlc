"""add LDAP synchronization audit tables

Revision ID: 20260910_003
Revises: 20260910_002
Create Date: 2026-09-10 00:20:00.000000
"""

from alembic import context, op
import sqlalchemy as sa


revision = "20260910_003"
down_revision = "20260910_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = _table_names()
    if tables is None or "ldap_sync_runs" not in tables:
        op.create_table(
            "ldap_sync_runs",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("initiated_by_user_id", sa.BigInteger(), nullable=True),
            sa.Column("status", sa.String(24), nullable=False, server_default="running"),
            sa.Column("total_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("bound_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("updated_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("skipped_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("failed_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["initiated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        )
    if tables is None or "ldap_sync_items" not in tables:
        op.create_table(
            "ldap_sync_items",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("run_id", sa.BigInteger(), nullable=False),
            sa.Column("external_id", sa.String(255), nullable=False),
            sa.Column("decision", sa.String(16), nullable=False),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=True),
            sa.Column("message", sa.String(500), nullable=True),
            sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.ForeignKeyConstraint(["run_id"], ["ldap_sync_runs.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        )
        op.create_index("ix_ldap_sync_items_run_id", "ldap_sync_items", ["run_id"])


def downgrade() -> None:
    tables = _table_names()
    if tables is None or "ldap_sync_items" in tables:
        op.drop_index("ix_ldap_sync_items_run_id", table_name="ldap_sync_items")
        op.drop_table("ldap_sync_items")
    if tables is None or "ldap_sync_runs" in tables:
        op.drop_table("ldap_sync_runs")


def _table_names() -> set[str] | None:
    try:
        if context.is_offline_mode():
            return None
    except (NameError, RuntimeError):
        return None
    return set(sa.inspect(op.get_bind()).get_table_names())
