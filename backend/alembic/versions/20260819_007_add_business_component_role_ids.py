"""add ID based business component role references

Revision ID: 20260819_007
Revises: 20260819_006
Create Date: 2026-08-19
"""

import json

from alembic import op
import sqlalchemy as sa


revision = "20260819_007"
down_revision = "20260819_006"
branch_labels = None
depends_on = None
ROLE_ALIASES = {"product_owner": "product_manager", "tech_lead": "development_lead", "test_lead": "tester"}


def _role_ids(value: str | None, role_by_key: dict[str, int], context: str) -> list[int]:
    keys = [item.strip() for item in (value or "").split(",") if item.strip()]
    normalized_keys = [ROLE_ALIASES.get(key, key) for key in keys]
    unknown = [key for key in normalized_keys if key not in role_by_key]
    if unknown:
        raise RuntimeError(f"{context} has unknown role(s): {', '.join(unknown)}")
    return [role_by_key[key] for key in normalized_keys]


def upgrade() -> None:
    op.add_column("business_component_members", sa.Column("role_id", sa.BigInteger(), nullable=True))
    op.add_column("business_component_transition_routes", sa.Column("eligible_role_ids", sa.JSON(), nullable=True))
    op.add_column("business_component_transition_routes", sa.Column("next_owner_role_ids", sa.JSON(), nullable=True))

    bind = op.get_bind()
    role_by_key = {
        row.role_key: row.id
        for row in bind.execute(sa.text("SELECT id, role_key FROM roles")).mappings()
    }
    for row in bind.execute(
        sa.text("SELECT id, component_role FROM business_component_members")
    ).mappings():
        role_ids = _role_ids(row.component_role, role_by_key, f"business_component_members {row.id}")
        if len(role_ids) != 1:
            raise RuntimeError(f"business_component_members {row.id} must have one role")
        bind.execute(
            sa.text("UPDATE business_component_members SET role_id = :role_id WHERE id = :id"),
            {"id": row.id, "role_id": role_ids[0]},
        )
    for row in bind.execute(
        sa.text("SELECT id, eligible_roles, next_owner_roles FROM business_component_transition_routes")
    ).mappings():
        bind.execute(
            sa.text(
                "UPDATE business_component_transition_routes SET eligible_role_ids = :eligible_role_ids, "
                "next_owner_role_ids = :next_owner_role_ids WHERE id = :id"
            ),
            {
                "id": row.id,
                "eligible_role_ids": json.dumps(_role_ids(row.eligible_roles, role_by_key, f"route {row.id} eligible")),
                "next_owner_role_ids": json.dumps(_role_ids(row.next_owner_roles, role_by_key, f"route {row.id} next owner")),
            },
        )


def downgrade() -> None:
    op.drop_column("business_component_transition_routes", "next_owner_role_ids")
    op.drop_column("business_component_transition_routes", "eligible_role_ids")
    op.drop_column("business_component_members", "role_id")
