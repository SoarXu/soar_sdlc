"""map internal capabilities to immutable business role IDs

Revision ID: 20260819_006
Revises: 20260819_005
Create Date: 2026-08-19
"""

from alembic import op
import sqlalchemy as sa


revision = "20260819_006"
down_revision = "20260819_005"
branch_labels = None
depends_on = None


CAPABILITIES = (
    "department_head",
    "project_owner",
    "product_manager",
    "development_lead",
    "developer",
    "tester",
    "viewer",
    "tech_lead",
    "test_lead",
)


def upgrade() -> None:
    bind = op.get_bind()
    if "role_capabilities" not in sa.inspect(bind).get_table_names():
        op.create_table(
            "role_capabilities",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("capability", sa.String(length=64), nullable=False, unique=True),
            sa.Column("role_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("create_time", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("update_time", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    roles = {
        row.role_key: row.id
        for row in bind.execute(sa.text("SELECT id, role_key FROM roles")).mappings()
    }
    for capability in CAPABILITIES:
        role_id = roles.get(capability)
        if role_id is not None and not bind.execute(
            sa.text("SELECT 1 FROM role_capabilities WHERE capability = :capability"),
            {"capability": capability},
        ).first():
            bind.execute(
                sa.text("INSERT INTO role_capabilities (capability, role_id) VALUES (:capability, :role_id)"),
                {"capability": capability, "role_id": role_id},
            )


def downgrade() -> None:
    op.drop_table("role_capabilities")
