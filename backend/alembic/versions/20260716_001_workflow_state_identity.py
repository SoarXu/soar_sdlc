"""migrate workflow runtime references to immutable state ids

Revision ID: 20260716_001
Revises: 20260713_002
Create Date: 2026-07-16 10:00:00.000000
"""

from collections.abc import Mapping, Sequence
from typing import Any, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "20260716_001"
down_revision: Union[str, None] = "20260713_002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_STATUS_GROUPS = {
    "requirement": (
        ("pending_assignment", "draft", "todo"),
        ("in_processing", "active", "validation_failed", "doing"),
        ("pending_confirmation", "pending_validation"),
        ("completed", "done"),
        ("canceled", "closed"),
    ),
    "task": (
        ("pending_assignment", "todo", "draft"),
        ("in_processing", "doing", "active"),
        ("pending_confirmation", "pending_validation"),
        ("completed", "done"),
        ("canceled", "closed"),
    ),
    "bug": (
        ("pending_handling", "open", "reopened", "suspended"),
        ("fixing",),
        ("pending_verification", "verifying", "resolved"),
        ("verified",),
        ("closed",),
    ),
}


def _status_candidates(object_type: str, status_value: str, owner_id: int | None = None) -> tuple[str, ...]:
    candidates = [status_value]
    for group in _STATUS_GROUPS.get(object_type, ()):
        if status_value in group:
            candidates.extend(group)
            break
    if status_value in {"draft", "todo"} and owner_id is not None:
        candidates.extend(("in_processing", "active", "doing"))
    return tuple(dict.fromkeys(candidates))


def _match_state_id(
    states: Sequence[Mapping[str, Any]],
    object_type: str,
    status_value: str,
    owner_id: int | None,
    object_id: int | None = None,
) -> int:
    for candidate in _status_candidates(object_type, status_value, owner_id):
        matches = [int(state["id"]) for state in states if state["status_key"] == candidate]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError(
                f"Cannot migrate {object_type} {object_id or '<unknown>'}: "
                f"state key {candidate!r} is ambiguous"
            )
    raise ValueError(
        f"Cannot migrate {object_type} {object_id or '<unknown>'} with status "
        f"{status_value!r}: no matching workflow state"
    )


def _initial_state_id(states: Sequence[Mapping[str, Any]], definition_id: int) -> int | None:
    matches = [int(state["id"]) for state in states if state["category"] == "start"]
    if not matches:
        return None
    if len(matches) != 1:
        raise ValueError(f"Workflow definition {definition_id} must have exactly one initial state")
    return matches[0]


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _add_column(table_name: str, column: sa.Column) -> None:
    if column.name not in _columns(table_name):
        op.add_column(table_name, column)


def _index_names(table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _add_index(name: str, table_name: str, columns: list[str]) -> None:
    if name not in _index_names(table_name):
        op.create_index(name, table_name, columns, unique=False)


def _foreign_key_names(table_name: str) -> set[str]:
    return {
        item["name"]
        for item in sa.inspect(op.get_bind()).get_foreign_keys(table_name)
        if item.get("name")
    }


def _add_foreign_key(
    name: str,
    source_table: str,
    target_table: str,
    source_columns: list[str],
    target_columns: list[str],
    ondelete: str,
) -> None:
    if name not in _foreign_key_names(source_table):
        op.create_foreign_key(
            name,
            source_table,
            target_table,
            source_columns,
            target_columns,
            ondelete=ondelete,
        )


def _states_by_definition(bind) -> dict[int, list[Mapping[str, Any]]]:
    rows = bind.execute(
        sa.text(
            "SELECT id, definition_id, status_key, status_name, category "
            "FROM workflow_states ORDER BY id"
        )
    ).mappings()
    grouped: dict[int, list[Mapping[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(int(row["definition_id"]), []).append(row)
    return grouped


def _definition_for_item(bind, object_type: str, project_id: int | None) -> int | None:
    config_id = None
    if project_id is not None:
        config_id = bind.execute(
            sa.text("SELECT assignee_rule_config_id FROM projects WHERE id = :project_id"),
            {"project_id": project_id},
        ).scalar_one_or_none()
    if config_id is not None:
        scoped = bind.execute(
            sa.text(
                "SELECT id FROM workflow_definitions "
                "WHERE object_type = :object_type AND scope_type = 'assignee_rule_config' "
                "AND scope_id = :scope_id AND enabled = 1 ORDER BY id DESC LIMIT 1"
            ),
            {"object_type": object_type, "scope_id": config_id},
        ).scalar_one_or_none()
        if scoped is not None:
            return int(scoped)
    default = bind.execute(
        sa.text(
            "SELECT id FROM workflow_definitions "
            "WHERE object_type = :object_type AND scope_type = 'system' "
            "AND is_default_template = 1 AND enabled = 1 ORDER BY id DESC LIMIT 1"
        ),
        {"object_type": object_type},
    ).scalar_one_or_none()
    return int(default) if default is not None else None


def _add_identity_columns() -> None:
    bigint = mysql.BIGINT(unsigned=True)
    _add_column("workflow_definitions", sa.Column("initial_state_id", bigint, nullable=True))
    _add_column("workflow_transitions", sa.Column("from_state_id", bigint, nullable=True))
    _add_column("workflow_transitions", sa.Column("to_state_id", bigint, nullable=True))

    for table_name in ("requirements", "tasks", "bugs"):
        _add_column(table_name, sa.Column("workflow_definition_id", bigint, nullable=True))
        _add_column(table_name, sa.Column("current_state_id", bigint, nullable=True))

    _add_column("status_operation_log", sa.Column("workflow_definition_id", bigint, nullable=True))
    _add_column("status_operation_log", sa.Column("from_state_id", bigint, nullable=True))
    _add_column("status_operation_log", sa.Column("to_state_id", bigint, nullable=True))
    _add_column("status_operation_log", sa.Column("from_state_name", sa.String(length=100), nullable=True))
    _add_column("status_operation_log", sa.Column("to_state_name", sa.String(length=100), nullable=True))

    _add_column(
        "assignee_rule_configs",
        sa.Column("lifecycle_status", sa.String(length=16), nullable=False, server_default="draft"),
    )
    op.execute(
        sa.text(
            "UPDATE assignee_rule_configs SET lifecycle_status = "
            "CASE WHEN enabled = 1 THEN 'enabled' ELSE 'disabled' END"
        )
    )


def _backfill_definitions_and_transitions(bind, states_by_definition) -> None:
    definitions = bind.execute(sa.text("SELECT id FROM workflow_definitions ORDER BY id")).mappings()
    for definition in definitions:
        definition_id = int(definition["id"])
        initial_state_id = _initial_state_id(states_by_definition.get(definition_id, []), definition_id)
        bind.execute(
            sa.text(
                "UPDATE workflow_definitions SET initial_state_id = :state_id WHERE id = :definition_id"
            ),
            {"state_id": initial_state_id, "definition_id": definition_id},
        )

    transitions = bind.execute(
        sa.text(
            "SELECT id, definition_id, from_status, to_status "
            "FROM workflow_transitions ORDER BY id"
        )
    ).mappings()
    for transition in transitions:
        definition_id = int(transition["definition_id"])
        states = states_by_definition.get(definition_id, [])
        by_key = {str(state["status_key"]): int(state["id"]) for state in states}
        try:
            from_state_id = by_key[str(transition["from_status"])]
            to_state_id = by_key[str(transition["to_status"])]
        except KeyError as exc:
            raise ValueError(
                f"Cannot migrate workflow transition {transition['id']} in definition "
                f"{definition_id}: state key {exc.args[0]!r} does not exist"
            ) from exc
        bind.execute(
            sa.text(
                "UPDATE workflow_transitions SET from_state_id = :from_state_id, "
                "to_state_id = :to_state_id WHERE id = :transition_id"
            ),
            {
                "from_state_id": from_state_id,
                "to_state_id": to_state_id,
                "transition_id": transition["id"],
            },
        )


def _backfill_work_items(bind, states_by_definition) -> None:
    for table_name, object_type in (("requirements", "requirement"), ("tasks", "task"), ("bugs", "bug")):
        rows = bind.execute(
            sa.text(f"SELECT id, project_id, owner_id, status FROM {table_name} ORDER BY id")
        ).mappings()
        for row in rows:
            definition_id = _definition_for_item(bind, object_type, row["project_id"])
            if definition_id is None:
                raise ValueError(
                    f"Cannot migrate {object_type} {row['id']}: no effective workflow definition"
                )
            state_id = _match_state_id(
                states_by_definition.get(definition_id, []),
                object_type,
                str(row["status"]),
                row["owner_id"],
                int(row["id"]),
            )
            bind.execute(
                sa.text(
                    f"UPDATE {table_name} SET workflow_definition_id = :definition_id, "
                    "current_state_id = :state_id WHERE id = :object_id"
                ),
                {"definition_id": definition_id, "state_id": state_id, "object_id": row["id"]},
            )


def _backfill_operation_log(bind, states_by_definition) -> None:
    state_names = {
        int(state["id"]): str(state["status_name"])
        for states in states_by_definition.values()
        for state in states
    }
    operations = bind.execute(
        sa.text(
            "SELECT id, object_type, object_id, from_status, to_status "
            "FROM status_operation_log ORDER BY id"
        )
    ).mappings()
    for operation in operations:
        object_type = str(operation["object_type"])
        definition_id = None
        from_state_id = None
        to_state_id = None
        if object_type in {"requirement", "task", "bug"}:
            table_name = {"requirement": "requirements", "task": "tasks", "bug": "bugs"}[object_type]
            item = bind.execute(
                sa.text(
                    f"SELECT workflow_definition_id, owner_id FROM {table_name} WHERE id = :object_id"
                ),
                {"object_id": operation["object_id"]},
            ).mappings().first()
            if item and item["workflow_definition_id"] is not None:
                definition_id = int(item["workflow_definition_id"])
                states = states_by_definition.get(definition_id, [])
                if operation["from_status"] is not None:
                    try:
                        from_state_id = _match_state_id(
                            states,
                            object_type,
                            str(operation["from_status"]),
                            item["owner_id"],
                            int(operation["object_id"]),
                        )
                    except ValueError:
                        pass
                try:
                    to_state_id = _match_state_id(
                        states,
                        object_type,
                        str(operation["to_status"]),
                        item["owner_id"],
                        int(operation["object_id"]),
                    )
                except ValueError:
                    pass
        from_name = state_names.get(from_state_id, operation["from_status"])
        to_name = state_names.get(to_state_id, operation["to_status"])
        bind.execute(
            sa.text(
                "UPDATE status_operation_log SET workflow_definition_id = :definition_id, "
                "from_state_id = :from_state_id, to_state_id = :to_state_id, "
                "from_state_name = :from_name, to_state_name = :to_name WHERE id = :operation_id"
            ),
            {
                "definition_id": definition_id,
                "from_state_id": from_state_id,
                "to_state_id": to_state_id,
                "from_name": from_name,
                "to_name": to_name,
                "operation_id": operation["id"],
            },
        )


def _add_indexes_and_foreign_keys() -> None:
    _add_index("ix_workflow_definitions_initial_state_id", "workflow_definitions", ["initial_state_id"])
    _add_index("ix_workflow_transitions_from_state_id", "workflow_transitions", ["from_state_id"])
    _add_index("ix_workflow_transitions_to_state_id", "workflow_transitions", ["to_state_id"])
    _add_index("ix_assignee_rule_configs_lifecycle_status", "assignee_rule_configs", ["lifecycle_status"])
    for table_name in ("requirements", "tasks", "bugs"):
        _add_index(f"ix_{table_name}_workflow_definition_id", table_name, ["workflow_definition_id"])
        _add_index(f"ix_{table_name}_current_state_id", table_name, ["current_state_id"])
    for column_name in ("workflow_definition_id", "from_state_id", "to_state_id"):
        _add_index(f"ix_status_operation_log_{column_name}", "status_operation_log", [column_name])

    _add_foreign_key(
        "fk_workflow_states_definition",
        "workflow_states",
        "workflow_definitions",
        ["definition_id"],
        ["id"],
        "CASCADE",
    )
    _add_foreign_key(
        "fk_workflow_transitions_definition",
        "workflow_transitions",
        "workflow_definitions",
        ["definition_id"],
        ["id"],
        "CASCADE",
    )
    _add_foreign_key(
        "fk_workflow_definitions_initial_state",
        "workflow_definitions",
        "workflow_states",
        ["initial_state_id"],
        ["id"],
        "RESTRICT",
    )
    for column_name in ("from_state_id", "to_state_id"):
        _add_foreign_key(
            f"fk_workflow_transitions_{column_name}",
            "workflow_transitions",
            "workflow_states",
            [column_name],
            ["id"],
            "RESTRICT",
        )
    for table_name in ("requirements", "tasks", "bugs"):
        _add_foreign_key(
            f"fk_{table_name}_workflow_definition",
            table_name,
            "workflow_definitions",
            ["workflow_definition_id"],
            ["id"],
            "RESTRICT",
        )
        _add_foreign_key(
            f"fk_{table_name}_current_state",
            table_name,
            "workflow_states",
            ["current_state_id"],
            ["id"],
            "RESTRICT",
        )
    _add_foreign_key(
        "fk_status_operation_log_workflow_definition",
        "status_operation_log",
        "workflow_definitions",
        ["workflow_definition_id"],
        ["id"],
        "SET NULL",
    )
    for column_name in ("from_state_id", "to_state_id"):
        _add_foreign_key(
            f"fk_status_operation_log_{column_name}",
            "status_operation_log",
            "workflow_states",
            [column_name],
            ["id"],
            "SET NULL",
        )


def upgrade() -> None:
    _add_identity_columns()
    bind = op.get_bind()
    states_by_definition = _states_by_definition(bind)
    _backfill_definitions_and_transitions(bind, states_by_definition)
    _backfill_work_items(bind, states_by_definition)
    _backfill_operation_log(bind, states_by_definition)
    _add_indexes_and_foreign_keys()


def downgrade() -> None:
    foreign_keys = {
        "workflow_definitions": ["fk_workflow_definitions_initial_state"],
        "workflow_states": ["fk_workflow_states_definition"],
        "workflow_transitions": [
            "fk_workflow_transitions_definition",
            "fk_workflow_transitions_from_state_id",
            "fk_workflow_transitions_to_state_id",
        ],
        "requirements": ["fk_requirements_workflow_definition", "fk_requirements_current_state"],
        "tasks": ["fk_tasks_workflow_definition", "fk_tasks_current_state"],
        "bugs": ["fk_bugs_workflow_definition", "fk_bugs_current_state"],
        "status_operation_log": [
            "fk_status_operation_log_workflow_definition",
            "fk_status_operation_log_from_state_id",
            "fk_status_operation_log_to_state_id",
        ],
    }
    for table_name, names in foreign_keys.items():
        existing = _foreign_key_names(table_name)
        for name in names:
            if name in existing:
                op.drop_constraint(name, table_name, type_="foreignkey")

    index_columns = {
        "workflow_definitions": ["initial_state_id"],
        "workflow_transitions": ["from_state_id", "to_state_id"],
        "requirements": ["workflow_definition_id", "current_state_id"],
        "tasks": ["workflow_definition_id", "current_state_id"],
        "bugs": ["workflow_definition_id", "current_state_id"],
        "status_operation_log": ["workflow_definition_id", "from_state_id", "to_state_id"],
        "assignee_rule_configs": ["lifecycle_status"],
    }
    for table_name, column_names in index_columns.items():
        existing = _index_names(table_name)
        for column_name in column_names:
            name = f"ix_{table_name}_{column_name}"
            if name in existing:
                op.drop_index(name, table_name=table_name)

    for table_name, column_names in (
        ("status_operation_log", ["to_state_name", "from_state_name", "to_state_id", "from_state_id", "workflow_definition_id"]),
        ("bugs", ["current_state_id", "workflow_definition_id"]),
        ("tasks", ["current_state_id", "workflow_definition_id"]),
        ("requirements", ["current_state_id", "workflow_definition_id"]),
        ("workflow_transitions", ["to_state_id", "from_state_id"]),
        ("workflow_definitions", ["initial_state_id"]),
        ("assignee_rule_configs", ["lifecycle_status"]),
    ):
        existing = _columns(table_name)
        for column_name in column_names:
            if column_name in existing:
                op.drop_column(table_name, column_name)
