"""add LDAP identity fields to users

Revision ID: 20260910_001
Revises: 20260826_001
Create Date: 2026-09-10 00:00:00.000000
"""

from alembic import context, op
import sqlalchemy as sa


revision = "20260910_001"
down_revision = "20260826_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns, indexes = _online_schema_state()
    additions = [
        sa.Column("employee_no", sa.String(length=64), nullable=True),
        sa.Column("auth_source", sa.String(length=16), nullable=False, server_default=sa.text("'local'")),
        sa.Column("ldap_external_id", sa.String(length=255), nullable=True),
        sa.Column("ldap_dn", sa.String(length=512), nullable=True),
        sa.Column("ldap_last_synced_at", sa.DateTime(), nullable=True),
        sa.Column(
            "active_employee_no",
            sa.String(length=64),
            sa.Computed(
                "CASE WHEN deleted = 0 AND is_active = 1 AND employee_no IS NOT NULL "
                "AND TRIM(employee_no) <> '' THEN employee_no ELSE NULL END",
                persisted=True,
            ),
            nullable=True,
        ),
    ]
    for column in additions:
        if columns is None or column.name not in columns:
            op.add_column("users", column)
    if indexes is None or "uq_users_active_employee_no" not in indexes:
        op.create_index("uq_users_active_employee_no", "users", ["active_employee_no"], unique=True)
    if indexes is None or "uq_users_ldap_external_id" not in indexes:
        op.create_unique_constraint("uq_users_ldap_external_id", "users", ["ldap_external_id"])
    op.execute(sa.text("UPDATE users SET auth_source = 'local' WHERE auth_source IS NULL OR auth_source = ''"))


def downgrade() -> None:
    columns, indexes = _online_schema_state()
    if indexes is None or "uq_users_ldap_external_id" in indexes:
        op.drop_constraint("uq_users_ldap_external_id", "users", type_="unique")
    if indexes is None or "uq_users_active_employee_no" in indexes:
        op.drop_index("uq_users_active_employee_no", table_name="users")
    for column_name in (
        "active_employee_no",
        "ldap_last_synced_at",
        "ldap_dn",
        "ldap_external_id",
        "auth_source",
        "employee_no",
    ):
        if columns is None or column_name in columns:
            op.drop_column("users", column_name)


def _online_schema_state() -> tuple[set[str] | None, set[str] | None]:
    try:
        if context.is_offline_mode():
            return None, None
    except (NameError, RuntimeError):
        return None, None
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("users")}
    indexes = {index["name"] for index in inspector.get_indexes("users")}
    return columns, indexes
