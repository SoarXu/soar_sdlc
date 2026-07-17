"""add workflow state identity to projects and iterations

Revision ID: 20260717_001
Revises: 20260716_002
Create Date: 2026-07-17 10:00:00.000000
"""

from collections.abc import Mapping, Sequence
import json
from typing import Any, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "20260717_001"
down_revision: Union[str, None] = "20260716_002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_MIGRATION_ORIGIN = revision


def _legacy_status_tables() -> dict[str, str]:
    return {"projects": "project", "iterations": "iteration"}


def _match_state_id(
    states: Sequence[Mapping[str, Any]],
    object_type: str,
    object_id: int,
    status_value: str,
) -> int:
    matches = [int(state["id"]) for state in states if state["status_key"] == status_value]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(
            f"Cannot migrate {object_type} {object_id}: state key {status_value!r} is ambiguous"
        )
    raise ValueError(
        f"Cannot migrate {object_type} {object_id} with status {status_value!r}: "
        "no matching workflow state"
    )


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _foreign_key_names(table_name: str) -> set[str]:
    return {
        item["name"]
        for item in sa.inspect(op.get_bind()).get_foreign_keys(table_name)
        if item.get("name")
    }


def _index_names(table_name: str) -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _system_definition(bind, object_type: str) -> int:
    rows = bind.execute(
        sa.text(
            "SELECT id FROM workflow_definitions "
            "WHERE object_type = :object_type AND scope_type = 'system' "
            "AND is_default_template = 1 AND enabled = 1 ORDER BY id"
        ),
        {"object_type": object_type},
    ).scalars().all()
    if len(rows) != 1:
        raise RuntimeError(
            f"Cannot migrate {object_type}: expected exactly one enabled system definition, found {len(rows)}"
        )
    return int(rows[0])


def _definition_states(bind, definition_id: int) -> list[Mapping[str, Any]]:
    return list(
        bind.execute(
            sa.text(
                "SELECT id, status_key FROM workflow_states "
                "WHERE definition_id = :definition_id ORDER BY id"
            ),
            {"definition_id": definition_id},
        ).mappings()
    )


def _backfill_table(bind, table_name: str, object_type: str) -> None:
    definition_id = _system_definition(bind, object_type)
    states = _definition_states(bind, definition_id)
    rows = bind.execute(
        sa.text(f"SELECT id, status FROM {table_name} ORDER BY id")
    ).mappings()
    for row in rows:
        state_id = _match_state_id(states, object_type, int(row["id"]), str(row["status"]))
        bind.execute(
            sa.text(
                f"UPDATE {table_name} SET workflow_definition_id = :definition_id, "
                "current_state_id = :state_id WHERE id = :object_id"
            ),
            {
                "definition_id": definition_id,
                "state_id": state_id,
                "object_id": int(row["id"]),
            },
        )


def _ensure_project_activate_transition(bind) -> None:
    definition_id = _system_definition(bind, "project")
    exists = bind.execute(
        sa.text(
            "SELECT transition_item.id FROM workflow_transitions transition_item "
            "JOIN workflow_states source_state ON source_state.id = transition_item.from_state_id "
            "JOIN workflow_states target_state ON target_state.id = transition_item.to_state_id "
            "WHERE transition_item.definition_id = :definition_id "
            "AND transition_item.action_key = 'activate' "
            "AND source_state.category = 'terminal' "
            "AND target_state.category <> 'terminal' LIMIT 1"
        ),
        {"definition_id": definition_id},
    ).scalar_one_or_none()
    if exists is not None:
        return
    states = _definition_states(bind, definition_id)
    closed_state_id = _match_state_id(states, "project", definition_id, "closed")
    active_state_id = _match_state_id(states, "project", definition_id, "active")
    state_keys = {int(item["id"]): str(item["status_key"]) for item in states}
    bind.execute(
        sa.text(
            "INSERT INTO workflow_transitions "
            "(definition_id, action_key, action_name, from_status, to_status, "
            "from_state_id, to_state_id, allowed_roles, enabled, sort_order, ui_config) "
            "VALUES (:definition_id, 'activate', '激活', :from_status, :to_status, "
            ":from_state_id, :to_state_id, '', 1, 100, :ui_config)"
        ),
        {
            "definition_id": definition_id,
            "from_status": state_keys[closed_state_id],
            "to_status": state_keys[active_state_id],
            "from_state_id": closed_state_id,
            "to_state_id": active_state_id,
            "ui_config": json.dumps({"migration_origin": _MIGRATION_ORIGIN}),
        },
    )


def upgrade() -> None:
    bigint = mysql.BIGINT(unsigned=True)
    for table_name in _legacy_status_tables():
        if "workflow_definition_id" not in _columns(table_name):
            op.add_column(table_name, sa.Column("workflow_definition_id", bigint, nullable=True))
        if "current_state_id" not in _columns(table_name):
            op.add_column(table_name, sa.Column("current_state_id", bigint, nullable=True))

    bind = op.get_bind()
    for table_name, object_type in _legacy_status_tables().items():
        _backfill_table(bind, table_name, object_type)
        for column_name in ("workflow_definition_id", "current_state_id"):
            index_name = f"ix_{table_name}_{column_name}"
            if index_name not in _index_names(table_name):
                op.create_index(index_name, table_name, [column_name], unique=False)
        foreign_keys = _foreign_key_names(table_name)
        definition_fk = f"fk_{table_name}_workflow_definition"
        state_fk = f"fk_{table_name}_current_state"
        if definition_fk not in foreign_keys:
            op.create_foreign_key(
                definition_fk,
                table_name,
                "workflow_definitions",
                ["workflow_definition_id"],
                ["id"],
                ondelete="RESTRICT",
            )
        if state_fk not in foreign_keys:
            op.create_foreign_key(
                state_fk,
                table_name,
                "workflow_states",
                ["current_state_id"],
                ["id"],
                ondelete="RESTRICT",
            )
    _ensure_project_activate_transition(bind)


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE transition_item FROM workflow_transitions transition_item "
            "JOIN workflow_definitions definition ON definition.id = transition_item.definition_id "
            "WHERE definition.object_type = 'project' AND definition.scope_type = 'system' "
            "AND transition_item.action_key = 'activate' "
            "AND JSON_UNQUOTE(JSON_EXTRACT(transition_item.ui_config, '$.migration_origin')) "
            "= :migration_origin"
        ),
        {"migration_origin": _MIGRATION_ORIGIN},
    )
    for table_name in reversed(tuple(_legacy_status_tables())):
        foreign_keys = _foreign_key_names(table_name)
        for constraint_name in (
            f"fk_{table_name}_current_state",
            f"fk_{table_name}_workflow_definition",
        ):
            if constraint_name in foreign_keys:
                op.drop_constraint(constraint_name, table_name, type_="foreignkey")
        indexes = _index_names(table_name)
        for column_name in ("current_state_id", "workflow_definition_id"):
            index_name = f"ix_{table_name}_{column_name}"
            if index_name in indexes:
                op.drop_index(index_name, table_name=table_name)
            if column_name in _columns(table_name):
                op.drop_column(table_name, column_name)
