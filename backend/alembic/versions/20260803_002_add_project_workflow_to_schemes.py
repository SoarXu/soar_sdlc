"""add project workflow definitions to existing schemes

Revision ID: 20260803_002
Revises: 20260803_001
Create Date: 2026-08-03 11:00:00.000000
"""

import json
from typing import Any, Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260803_002"
down_revision: Union[str, None] = "20260803_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _json_value(value: Any) -> str | None:
    if value is None or isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def upgrade() -> None:
    bind = op.get_bind()
    source = bind.execute(
        sa.text(
            "SELECT id, initial_state_id FROM workflow_definitions "
            "WHERE object_type = 'project' AND scope_type = 'system' "
            "AND is_default_template = 1 AND enabled = 1 ORDER BY id DESC LIMIT 1"
        )
    ).mappings().first()
    if not source:
        raise RuntimeError("Default system project workflow definition not found")

    source_states = list(
        bind.execute(
            sa.text(
                "SELECT id, status_name, category, terminal_kind, color, x, y, sort_order, enabled "
                "FROM workflow_states WHERE definition_id = :definition_id ORDER BY id"
            ),
            {"definition_id": source["id"]},
        ).mappings()
    )
    source_transitions = list(
        bind.execute(
            sa.text(
                "SELECT action_key, action_name, from_state_id, to_state_id, allowed_roles, handler_rule, "
                "trigger_config, condition_config, validator_config, post_action_config, ui_config, form_config, "
                "diagram_config, enabled, sort_order "
                "FROM workflow_transitions WHERE definition_id = :definition_id ORDER BY id"
            ),
            {"definition_id": source["id"]},
        ).mappings()
    )
    configs = list(bind.execute(sa.text("SELECT id, name FROM assignee_rule_configs ORDER BY id")).mappings())

    for config in configs:
        exists = bind.execute(
            sa.text(
                "SELECT 1 FROM workflow_definitions WHERE object_type = 'project' "
                "AND scope_type = 'assignee_rule_config' AND scope_id = :scope_id LIMIT 1"
            ),
            {"scope_id": config["id"]},
        ).first()
        if exists:
            continue

        definition_result = bind.execute(
            sa.text(
                "INSERT INTO workflow_definitions "
                "(name, object_type, scope_type, scope_id, is_default_template, enabled, version) "
                "VALUES (:name, 'project', 'assignee_rule_config', :scope_id, 0, 1, 1)"
            ),
            {"name": f"{config['name']}-项目工作流", "scope_id": config["id"]},
        )
        definition_id = definition_result.lastrowid
        state_id_map: dict[int, int] = {}
        for state in source_states:
            state_result = bind.execute(
                sa.text(
                    "INSERT INTO workflow_states "
                    "(definition_id, status_name, category, terminal_kind, color, x, y, sort_order, enabled) "
                    "VALUES (:definition_id, :status_name, :category, :terminal_kind, :color, :x, :y, :sort_order, :enabled)"
                ),
                {"definition_id": definition_id, **dict(state)},
            )
            state_id_map[state["id"]] = state_result.lastrowid

        bind.execute(
            sa.text("UPDATE workflow_definitions SET initial_state_id = :initial_state_id WHERE id = :definition_id"),
            {"definition_id": definition_id, "initial_state_id": state_id_map[source["initial_state_id"]]},
        )
        for transition in source_transitions:
            values = dict(transition)
            for key in (
                "handler_rule",
                "trigger_config",
                "condition_config",
                "validator_config",
                "post_action_config",
                "ui_config",
                "form_config",
                "diagram_config",
            ):
                values[key] = _json_value(values[key])
            values.update(
                {
                    "definition_id": definition_id,
                    "from_state_id": state_id_map[transition["from_state_id"]],
                    "to_state_id": state_id_map[transition["to_state_id"]],
                }
            )
            bind.execute(
                sa.text(
                    "INSERT INTO workflow_transitions "
                    "(definition_id, action_key, action_name, from_state_id, to_state_id, allowed_roles, handler_rule, "
                    "trigger_config, condition_config, validator_config, post_action_config, ui_config, form_config, "
                    "diagram_config, enabled, sort_order) "
                    "VALUES (:definition_id, :action_key, :action_name, :from_state_id, :to_state_id, :allowed_roles, "
                    ":handler_rule, :trigger_config, :condition_config, :validator_config, :post_action_config, "
                    ":ui_config, :form_config, :diagram_config, :enabled, :sort_order)"
                ),
                values,
            )


def downgrade() -> None:
    # Scheme project definitions may have been edited after this migration.
    pass
