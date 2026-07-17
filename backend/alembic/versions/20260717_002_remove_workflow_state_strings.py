"""remove legacy workflow state string identity

Revision ID: 20260717_002
Revises: 20260717_001
Create Date: 2026-07-17 16:00:00.000000
"""

from collections.abc import Mapping, Sequence
import json
from typing import Any, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "20260717_002"
down_revision: Union[str, None] = "20260717_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _legacy_columns() -> dict[str, tuple[str, ...]]:
    return {
        "projects": ("status",),
        "iterations": ("status",),
        "workflow_states": ("status_key",),
        "workflow_transitions": ("from_status", "to_status"),
    }


def _legacy_handler_rule_table() -> str:
    return "handler_transition_rules"


def _core_work_item_tables() -> tuple[str, ...]:
    return ("requirements", "tasks", "bugs", "projects", "iterations")


def _format_audit_issues(issues: Sequence[Mapping[str, Any]]) -> str:
    entries: list[str] = []
    for issue in sorted(issues, key=lambda item: (str(item["issue"]), str(item["table"]))):
        ids = ",".join(str(value) for value in sorted({int(value) for value in issue["ids"]}))
        entries.append(f'{issue["issue"]}[{issue["table"]}]={ids}')
    return "Workflow state finalization audit failed: " + "; ".join(entries)


def _handler_rule_payload(rule: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "target_type": rule.get("target_type") or "keep_current",
        "target_roles": rule.get("target_roles") or "",
        "fallback_type": rule.get("fallback_type") or "keep_current",
        "fallback_roles": rule.get("fallback_roles") or "",
    }


def _json_mapping(value: Any) -> dict[str, Any]:
    if not value:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        parsed = json.loads(value)
        return dict(parsed) if isinstance(parsed, Mapping) else {}
    return {}


def _plan_handler_rule_migration(
    rules: Sequence[Mapping[str, Any]],
    transitions: Sequence[Mapping[str, Any]],
) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]]]:
    updates: dict[int, dict[str, Any]] = {}
    issue_ids: dict[str, list[int]] = {}
    transitions_by_id = {int(item["id"]): item for item in transitions}

    for rule in sorted(rules, key=lambda item: int(item["id"])):
        matches = [
            transition
            for transition in transitions
            if int(transition["config_id"]) == int(rule["config_id"])
            and str(transition["object_type"]) == str(rule["object_type"])
            and str(transition["action"]) == str(rule["action"])
            and (
                rule.get("from_status") is None
                or str(transition["from_status"]) == str(rule["from_status"])
            )
            and (
                rule.get("to_status") is None
                or str(transition["to_status"]) == str(rule["to_status"])
            )
        ]
        if not matches:
            issue_ids.setdefault("unmapped_handler_rule", []).append(int(rule["id"]))
            continue
        if len(matches) > 1:
            issue_ids.setdefault("ambiguous_handler_rule", []).append(int(rule["id"]))
            continue

        transition_id = int(matches[0]["id"])
        legacy_payload = _handler_rule_payload(rule)
        existing = updates.get(transition_id)
        if existing is None:
            existing = _json_mapping(transitions_by_id[transition_id].get("handler_rule"))
        if not existing:
            updates[transition_id] = legacy_payload
            continue
        if _handler_rule_payload(existing) != legacy_payload:
            issue_ids.setdefault("conflicting_handler_rule", []).append(int(rule["id"]))

    issues = [
        {
            "issue": issue,
            "table": _legacy_handler_rule_table(),
            "ids": sorted(set(ids)),
        }
        for issue, ids in sorted(issue_ids.items())
    ]
    return ({}, issues) if issues else (updates, [])


def _legacy_rule_from_transition(transition: Mapping[str, Any]) -> dict[str, Any] | None:
    handler_rule = _json_mapping(transition.get("handler_rule"))
    if not handler_rule or transition.get("config_id") is None:
        return None
    payload = _handler_rule_payload(handler_rule)
    if not all(isinstance(payload[field], str) for field in payload):
        return None
    return {
        "config_id": int(transition["config_id"]),
        "rule_type": "advanced",
        "object_type": str(transition["object_type"]),
        "action": str(transition["action"]),
        "from_status": transition.get("from_status"),
        "to_status": transition.get("to_status"),
        **payload,
        "enabled": 1,
    }


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _column_names(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _issue_ids(bind, query: str) -> list[int]:
    return [int(value) for value in bind.execute(sa.text(query)).scalars().all()]


def _collect_audit_issues(bind) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []

    for table_name in _core_work_item_tables():
        null_ids = _issue_ids(
            bind,
            f"SELECT id FROM {table_name} "
            "WHERE workflow_definition_id IS NULL OR current_state_id IS NULL ORDER BY id",
        )
        if null_ids:
            issues.append(
                {"issue": "null_workflow_reference", "table": table_name, "ids": null_ids}
            )
        invalid_ids = _issue_ids(
            bind,
            f"SELECT item.id FROM {table_name} item "
            "LEFT JOIN workflow_definitions definition "
            "ON definition.id = item.workflow_definition_id "
            "LEFT JOIN workflow_states state ON state.id = item.current_state_id "
            "WHERE item.workflow_definition_id IS NOT NULL "
            "AND item.current_state_id IS NOT NULL "
            "AND (definition.id IS NULL OR state.id IS NULL "
            "OR state.definition_id <> item.workflow_definition_id) ORDER BY item.id",
        )
        if invalid_ids:
            issues.append(
                {
                    "issue": "invalid_current_state_definition",
                    "table": table_name,
                    "ids": invalid_ids,
                }
            )

    initial_ids = _issue_ids(
        bind,
        "SELECT definition.id FROM workflow_definitions definition "
        "LEFT JOIN workflow_states state ON state.id = definition.initial_state_id "
        "WHERE definition.initial_state_id IS NOT NULL "
        "AND (state.id IS NULL OR state.definition_id <> definition.id OR state.enabled <> 1) "
        "ORDER BY definition.id",
    )
    if initial_ids:
        issues.append(
            {
                "issue": "invalid_initial_state_definition",
                "table": "workflow_definitions",
                "ids": initial_ids,
            }
        )

    transition_ids = _issue_ids(
        bind,
        "SELECT transition_row.id FROM workflow_transitions transition_row "
        "LEFT JOIN workflow_states source ON source.id = transition_row.from_state_id "
        "LEFT JOIN workflow_states target ON target.id = transition_row.to_state_id "
        "WHERE transition_row.from_state_id IS NULL OR transition_row.to_state_id IS NULL "
        "OR source.id IS NULL OR target.id IS NULL "
        "OR source.definition_id <> transition_row.definition_id "
        "OR target.definition_id <> transition_row.definition_id "
        "ORDER BY transition_row.id",
    )
    if transition_ids:
        issues.append(
            {
                "issue": "invalid_transition_definition",
                "table": "workflow_transitions",
                "ids": transition_ids,
            }
        )

    return issues


def _handler_rule_migration_plan(bind):
    if _legacy_handler_rule_table() not in _table_names():
        return {}, []
    rules = list(
        bind.execute(
            sa.text(
                "SELECT id, config_id, object_type, action, from_status, to_status, "
                "target_type, target_roles, fallback_type, fallback_roles "
                "FROM handler_transition_rules WHERE enabled = 1 ORDER BY id"
            )
        ).mappings()
    )
    transitions = list(
        bind.execute(
            sa.text(
                "SELECT transition_row.id, definition.scope_id AS config_id, "
                "definition.object_type, transition_row.action_key AS action, "
                "source.status_key AS from_status, target.status_key AS to_status, "
                "transition_row.handler_rule "
                "FROM workflow_transitions transition_row "
                "JOIN workflow_definitions definition ON definition.id = transition_row.definition_id "
                "JOIN workflow_states source ON source.id = transition_row.from_state_id "
                "JOIN workflow_states target ON target.id = transition_row.to_state_id "
                "WHERE definition.scope_type = 'assignee_rule_config' "
                "AND definition.scope_id IS NOT NULL ORDER BY transition_row.id"
            )
        ).mappings()
    )
    return _plan_handler_rule_migration(rules, transitions)


def _audit_or_raise(bind, extra_issues: Sequence[Mapping[str, Any]] = ()) -> None:
    issues = [*_collect_audit_issues(bind), *extra_issues]
    if issues:
        raise RuntimeError(_format_audit_issues(issues))


def upgrade() -> None:
    bind = op.get_bind()
    handler_updates, handler_issues = _handler_rule_migration_plan(bind)
    _audit_or_raise(bind, handler_issues)
    for transition_id, handler_rule in sorted(handler_updates.items()):
        bind.execute(
            sa.text(
                "UPDATE workflow_transitions SET handler_rule = :handler_rule WHERE id = :transition_id"
            ),
            {
                "handler_rule": json.dumps(handler_rule, ensure_ascii=False, sort_keys=True),
                "transition_id": transition_id,
            },
        )
    bigint = mysql.BIGINT(unsigned=True)

    for table_name in ("projects", "iterations"):
        op.alter_column(
            table_name,
            "workflow_definition_id",
            existing_type=bigint,
            nullable=False,
        )
        op.alter_column(
            table_name,
            "current_state_id",
            existing_type=bigint,
            nullable=False,
        )
    for column_name in ("from_state_id", "to_state_id"):
        op.alter_column(
            "workflow_transitions",
            column_name,
            existing_type=bigint,
            nullable=False,
        )

    if "idx_wft_action" in _index_names("workflow_transitions"):
        op.drop_index("idx_wft_action", table_name="workflow_transitions")
    op.create_index(
        "idx_wft_action_state",
        "workflow_transitions",
        ["definition_id", "action_key", "from_state_id", "to_state_id"],
        unique=False,
    )
    if "idx_wfs_status" in _index_names("workflow_states"):
        op.drop_index("idx_wfs_status", table_name="workflow_states")

    for table_name, columns in _legacy_columns().items():
        for column_name in columns:
            if column_name in _column_names(table_name):
                op.drop_column(table_name, column_name)
    if _legacy_handler_rule_table() in _table_names():
        op.drop_table(_legacy_handler_rule_table())


def downgrade() -> None:
    bigint = mysql.BIGINT(unsigned=True)

    op.add_column("projects", sa.Column("status", sa.String(length=32), nullable=True))
    op.add_column("iterations", sa.Column("status", sa.String(length=32), nullable=True))
    op.add_column("workflow_states", sa.Column("status_key", sa.String(length=64), nullable=True))
    op.add_column("workflow_transitions", sa.Column("from_status", sa.String(length=64), nullable=True))
    op.add_column("workflow_transitions", sa.Column("to_status", sa.String(length=64), nullable=True))

    bind = op.get_bind()
    bind.execute(sa.text("UPDATE workflow_states SET status_key = CONCAT('state_', id)"))
    for table_name in ("projects", "iterations"):
        bind.execute(
            sa.text(
                f"UPDATE {table_name} item JOIN workflow_states state "
                "ON state.id = item.current_state_id SET item.status = state.status_key"
            )
        )
    bind.execute(
        sa.text(
            "UPDATE workflow_transitions transition_row "
            "JOIN workflow_states source ON source.id = transition_row.from_state_id "
            "JOIN workflow_states target ON target.id = transition_row.to_state_id "
            "SET transition_row.from_status = source.status_key, "
            "transition_row.to_status = target.status_key"
        )
    )
    for table_name, columns in _legacy_columns().items():
        for column_name in columns:
            op.alter_column(
                table_name,
                column_name,
                existing_type=sa.String(length=32 if table_name in {"projects", "iterations"} else 64),
                nullable=False,
            )

    if "idx_wft_action_state" in _index_names("workflow_transitions"):
        op.drop_index("idx_wft_action_state", table_name="workflow_transitions")
    op.create_index(
        "idx_wft_action",
        "workflow_transitions",
        ["definition_id", "action_key", "from_status", "to_status"],
        unique=False,
    )
    op.create_index(
        "idx_wfs_status",
        "workflow_states",
        ["definition_id", "status_key"],
        unique=False,
    )

    op.create_table(
        _legacy_handler_rule_table(),
        sa.Column("id", bigint, nullable=False, autoincrement=True),
        sa.Column("config_id", bigint, nullable=False),
        sa.Column("rule_type", sa.String(length=32), nullable=False, server_default="advanced"),
        sa.Column("object_type", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=True),
        sa.Column("target_type", sa.String(length=64), nullable=False, server_default="keep_current"),
        sa.Column("target_roles", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("fallback_type", sa.String(length=64), nullable=False, server_default="keep_current"),
        sa.Column("fallback_roles", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("create_time", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column(
            "update_time",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_htr_config", _legacy_handler_rule_table(), ["config_id"], unique=False)
    op.create_index(
        "idx_htr_match",
        _legacy_handler_rule_table(),
        ["config_id", "object_type", "action", "enabled"],
        unique=False,
    )
    op.create_index(
        "idx_htr_rule_type",
        _legacy_handler_rule_table(),
        ["config_id", "rule_type", "object_type", "enabled"],
        unique=False,
    )
    _rebuild_legacy_handler_rules(bind)

    for table_name in ("projects", "iterations"):
        op.alter_column(
            table_name,
            "workflow_definition_id",
            existing_type=bigint,
            nullable=True,
        )
        op.alter_column(
            table_name,
            "current_state_id",
            existing_type=bigint,
            nullable=True,
        )
    for column_name in ("from_state_id", "to_state_id"):
        op.alter_column(
            "workflow_transitions",
            column_name,
            existing_type=bigint,
            nullable=True,
        )


def _rebuild_legacy_handler_rules(bind) -> None:
    transitions = bind.execute(
        sa.text(
            "SELECT transition_row.id, definition.scope_id AS config_id, "
            "definition.object_type, transition_row.action_key AS action, "
            "source.status_key AS from_status, target.status_key AS to_status, "
            "transition_row.handler_rule "
            "FROM workflow_transitions transition_row "
            "JOIN workflow_definitions definition ON definition.id = transition_row.definition_id "
            "JOIN workflow_states source ON source.id = transition_row.from_state_id "
            "JOIN workflow_states target ON target.id = transition_row.to_state_id "
            "WHERE definition.scope_type = 'assignee_rule_config' "
            "AND definition.scope_id IS NOT NULL "
            "AND transition_row.handler_rule IS NOT NULL ORDER BY transition_row.id"
        )
    ).mappings()
    insert_statement = sa.text(
        "INSERT INTO handler_transition_rules "
        "(config_id, rule_type, object_type, action, from_status, to_status, "
        "target_type, target_roles, fallback_type, fallback_roles, enabled) "
        "VALUES (:config_id, :rule_type, :object_type, :action, :from_status, :to_status, "
        ":target_type, :target_roles, :fallback_type, :fallback_roles, :enabled)"
    )
    for transition in transitions:
        legacy_rule = _legacy_rule_from_transition(transition)
        if legacy_rule is not None:
            bind.execute(insert_statement, legacy_rule)
