"""add LDAP integration configuration

Revision ID: 20260910_002
Revises: 20260910_001
Create Date: 2026-09-10 00:10:00.000000
"""

from alembic import context, op
import sqlalchemy as sa


revision = "20260910_002"
down_revision = "20260910_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    table_exists = _table_exists()
    if table_exists is True:
        if "ck_ldap_integration_config_singleton" not in _check_constraint_names():
            op.alter_column(
                "ldap_integration_config",
                "id",
                existing_type=sa.BigInteger(),
                existing_nullable=False,
                autoincrement=False,
            )
            op.create_check_constraint(
                "ck_ldap_integration_config_singleton",
                "ldap_integration_config",
                "id = 1",
            )
        return
    op.create_table(
        "ldap_integration_config",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("protocol", sa.String(8), nullable=False, server_default="ldaps"),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False, server_default=sa.text("636")),
        sa.Column("connect_timeout", sa.Integer(), nullable=False, server_default=sa.text("5")),
        sa.Column("base_dn", sa.String(512), nullable=False),
        sa.Column("bind_username", sa.String(512), nullable=False),
        sa.Column("bind_password_encrypted", sa.Text(), nullable=False),
        sa.Column("user_base_dn", sa.String(512), nullable=True),
        sa.Column("user_filter", sa.String(1000), nullable=False),
        sa.Column("exclude_disabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("page_size", sa.Integer(), nullable=False, server_default=sa.text("50")),
        sa.Column("username_attribute", sa.String(64), nullable=False, server_default="sAMAccountName"),
        sa.Column("employee_no_attribute", sa.String(64), nullable=False, server_default="employeeID"),
        sa.Column("full_name_attribute", sa.String(64), nullable=False, server_default="displayName"),
        sa.Column("email_attribute", sa.String(64), nullable=False, server_default="mail"),
        sa.Column("mobile_attribute", sa.String(64), nullable=False, server_default="mobile"),
        sa.Column("department_attribute", sa.String(64), nullable=False, server_default="department"),
        sa.Column("external_id_attribute", sa.String(64), nullable=False, server_default="objectGUID"),
        sa.Column("tested_fingerprint", sa.String(64), nullable=True),
        sa.Column("tested_at", sa.DateTime(), nullable=True),
        sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("update_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("id = 1", name="ck_ldap_integration_config_singleton"),
    )


def downgrade() -> None:
    if _table_exists() is not False:
        op.drop_table("ldap_integration_config")


def _table_exists() -> bool | None:
    try:
        if context.is_offline_mode():
            return None
    except (NameError, RuntimeError):
        return None
    return "ldap_integration_config" in sa.inspect(op.get_bind()).get_table_names()


def _check_constraint_names() -> set[str]:
    return {
        constraint["name"]
        for constraint in sa.inspect(op.get_bind()).get_check_constraints("ldap_integration_config")
        if constraint.get("name")
    }
