"""remove legacy text role storage after ID backfill

Revision ID: 20260819_008
Revises: 20260819_007
Create Date: 2026-08-19
"""

import json

from alembic import op
import sqlalchemy as sa


revision = "20260819_008"
down_revision = "20260819_007"
branch_labels = None
depends_on = None


IDENTITIES = {"system_admin", "project_member", "current_handler", "owner", "creator", "reporter", "proposer"}
ROLE_ALIASES = {"product_owner": "product_manager", "tech_lead": "development_lead", "test_lead": "tester"}


def _json(value):
    if isinstance(value, dict):
        return dict(value)
    return json.loads(value) or {} if value else {}


def _role_ids(value, role_by_key, context):
    values = value if isinstance(value, list) else str(value or "").split(",")
    names = [str(item).strip() for item in values if str(item).strip()]
    normalized_names = [ROLE_ALIASES.get(name, name) for name in names]
    unknown = [name for name in normalized_names if name not in IDENTITIES and name not in role_by_key]
    if unknown:
        raise RuntimeError(f"{context} has unknown role(s): {', '.join(unknown)}")
    return [role_by_key[name] for name in normalized_names if name not in IDENTITIES]


def _insert_role_refs(bind, transition_id, purpose, role_ids):
    existing = {
        (row.purpose, row.role_id)
        for row in bind.execute(
            sa.text("SELECT purpose, role_id FROM workflow_transition_roles WHERE transition_id = :transition_id"),
            {"transition_id": transition_id},
        ).mappings()
    }
    for index, role_id in enumerate(role_ids):
        if (purpose, role_id) not in existing:
            bind.execute(
                sa.text(
                    "INSERT INTO workflow_transition_roles (transition_id, role_id, purpose, sort_order) "
                    "VALUES (:transition_id, :role_id, :purpose, :sort_order)"
                ),
                {"transition_id": transition_id, "role_id": role_id, "purpose": purpose, "sort_order": index},
            )


def upgrade() -> None:
    bind = op.get_bind()
    duplicates = bind.execute(
        sa.text("SELECT role_name FROM roles GROUP BY role_name HAVING COUNT(*) > 1")
    ).scalars().all()
    if duplicates:
        raise RuntimeError(f"roles has duplicate names: {', '.join(duplicates)}")
    role_by_key = {
        row.role_key: row.id
        for row in bind.execute(sa.text("SELECT id, role_key FROM roles")).mappings()
    }

    missing_project_roles = bind.execute(
        sa.text("SELECT id FROM project_members WHERE role_id IS NULL")
    ).scalars().all()
    if missing_project_roles:
        raise RuntimeError(f"project_members missing role_id: {', '.join(str(item) for item in missing_project_roles)}")
    missing_component_roles = bind.execute(
        sa.text("SELECT id FROM business_component_members WHERE role_id IS NULL")
    ).scalars().all()
    if missing_component_roles:
        raise RuntimeError(f"business_component_members missing role_id: {', '.join(str(item) for item in missing_component_roles)}")

    rows = bind.execute(
        sa.text("SELECT id, allowed_roles, handler_rule, condition_config FROM workflow_transitions")
    ).mappings()
    for row in rows:
        allowed_names = [item.strip() for item in (row.allowed_roles or "").split(",") if item.strip()]
        allowed_identities = [name for name in allowed_names if name in IDENTITIES]
        _insert_role_refs(bind, row.id, "allowed", _role_ids(allowed_names, role_by_key, f"workflow transition {row.id} allowed"))
        rule = _json(row.handler_rule)
        _insert_role_refs(bind, row.id, "target", _role_ids(rule.pop("target_roles", ""), role_by_key, f"workflow transition {row.id} target"))
        _insert_role_refs(bind, row.id, "fallback", _role_ids(rule.pop("fallback_roles", ""), role_by_key, f"workflow transition {row.id} fallback"))
        rule.pop("manual_owner_roles", None)
        condition = _json(row.condition_config)
        override_ids = _role_ids(condition.pop("allow_override_roles", []), role_by_key, f"workflow transition {row.id} override")
        if override_ids:
            condition["allow_override_role_ids"] = override_ids
        bind.execute(
            sa.text(
                "UPDATE workflow_transitions SET allowed_roles = :allowed_roles, handler_rule = :handler_rule, "
                "condition_config = :condition_config WHERE id = :id"
            ),
            {
                "id": row.id,
                "allowed_roles": ",".join(allowed_identities),
                "handler_rule": json.dumps(rule),
                "condition_config": json.dumps(condition) if condition else None,
            },
        )

    op.alter_column("project_members", "role_id", existing_type=sa.BigInteger(), nullable=False)
    op.alter_column("business_component_members", "role_id", existing_type=sa.BigInteger(), nullable=False)
    op.create_unique_constraint("uk_roles_role_name", "roles", ["role_name"])
    op.drop_table("user_roles")
    op.drop_column("project_members", "project_role")
    op.drop_column("roles", "role_key")
    for column in (
        "requirement_owner_roles",
        "task_owner_roles",
        "test_case_tester_roles",
        "test_run_owner_roles",
        "bug_owner_roles",
    ):
        op.drop_column("assignee_rule_configs", column)
    op.drop_column("business_component_members", "component_role")
    op.drop_column("business_component_transition_routes", "eligible_roles")
    op.drop_column("business_component_transition_routes", "next_owner_roles")


def downgrade() -> None:
    raise RuntimeError("Legacy text role columns cannot be reconstructed from role IDs")
