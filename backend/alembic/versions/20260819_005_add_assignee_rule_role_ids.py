"""add ID based assignee rule role references

Revision ID: 20260819_005
Revises: 20260819_004
Create Date: 2026-08-19
"""

import json

from alembic import op
import sqlalchemy as sa


revision = "20260819_005"
down_revision = "20260819_004"
branch_labels = None
depends_on = None


ROLE_FIELDS = (
    "requirement_owner",
    "task_owner",
    "test_case_tester",
    "test_run_owner",
    "bug_owner",
)
ROLE_ALIASES = {"product_owner": "product_manager", "tech_lead": "development_lead", "test_lead": "tester"}


def upgrade() -> None:
    for prefix in ROLE_FIELDS:
        op.add_column(
            "assignee_rule_configs",
            sa.Column(f"{prefix}_role_ids", sa.JSON(), nullable=True),
        )

    bind = op.get_bind()
    role_by_key = {
        row.role_key: row.id
        for row in bind.execute(sa.text("SELECT id, role_key FROM roles")).mappings()
    }
    rows = bind.execute(
        sa.text(
            "SELECT id, requirement_owner_roles, task_owner_roles, test_case_tester_roles, "
            "test_run_owner_roles, bug_owner_roles FROM assignee_rule_configs"
        )
    ).mappings()
    for row in rows:
        updates = {}
        for prefix in ROLE_FIELDS:
            legacy_value = row[f"{prefix}_roles"] or ""
            keys = [item.strip() for item in legacy_value.split(",") if item.strip()]
            normalized_keys = [ROLE_ALIASES.get(key, key) for key in keys]
            unknown = [key for key in normalized_keys if key not in role_by_key]
            if unknown:
                raise RuntimeError(
                    f"assignee_rule_configs {row.id} has unknown {prefix} role(s): {', '.join(unknown)}"
                )
            updates[f"{prefix}_role_ids"] = json.dumps([role_by_key[key] for key in normalized_keys])
        bind.execute(
            sa.text(
                "UPDATE assignee_rule_configs SET "
                "requirement_owner_role_ids = :requirement_owner_role_ids, "
                "task_owner_role_ids = :task_owner_role_ids, "
                "test_case_tester_role_ids = :test_case_tester_role_ids, "
                "test_run_owner_role_ids = :test_run_owner_role_ids, "
                "bug_owner_role_ids = :bug_owner_role_ids WHERE id = :id"
            ),
            {"id": row.id, **updates},
        )


def downgrade() -> None:
    for prefix in reversed(ROLE_FIELDS):
        op.drop_column("assignee_rule_configs", f"{prefix}_role_ids")
