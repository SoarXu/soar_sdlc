"""Read-only audit for workflow state identity references."""

from __future__ import annotations

import json
from pathlib import Path
import sys

from sqlalchemy import inspect, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import engine


CORE_TABLES = ("requirements", "tasks", "bugs", "projects", "iterations")
LEGACY_COLUMNS = {
    "projects": ("status",),
    "iterations": ("status",),
    "workflow_states": ("status_key",),
    "workflow_transitions": ("from_status", "to_status"),
}
REQUIRED_ID_COLUMNS = {
    **{
        table_name: ("workflow_definition_id", "current_state_id")
        for table_name in CORE_TABLES
    },
    "workflow_transitions": ("from_state_id", "to_state_id"),
}


def collect_issues() -> list[dict[str, int | str]]:
    issues: list[dict[str, int | str]] = []
    inspector = inspect(engine)
    table_columns = {
        table_name: {column["name"] for column in inspector.get_columns(table_name)}
        for table_name in (*CORE_TABLES, "workflow_states", "workflow_transitions")
    }
    column_metadata = {
        table_name: {column["name"]: column for column in inspector.get_columns(table_name)}
        for table_name in REQUIRED_ID_COLUMNS
    }
    for table_name, columns in LEGACY_COLUMNS.items():
        for column_name in columns:
            if column_name in table_columns[table_name]:
                issues.append(
                    {
                        "issue": "legacy_workflow_column",
                        "table": f"{table_name}.{column_name}",
                        "count": 1,
                    }
                )
    if "handler_transition_rules" in inspector.get_table_names():
        issues.append(
            {"issue": "legacy_handler_rule_table", "table": "handler_transition_rules", "count": 1}
        )
    for table_name, column_names in REQUIRED_ID_COLUMNS.items():
        indexes = inspector.get_indexes(table_name)
        foreign_keys = inspector.get_foreign_keys(table_name)
        indexed_columns = {column for index in indexes for column in index["column_names"]}
        foreign_key_columns = {
            column
            for foreign_key in foreign_keys
            for column in foreign_key["constrained_columns"]
        }
        for column_name in column_names:
            if column_metadata[table_name][column_name]["nullable"]:
                issues.append(
                    {
                        "issue": "nullable_workflow_identity_column",
                        "table": f"{table_name}.{column_name}",
                        "count": 1,
                    }
                )
            if column_name not in indexed_columns:
                issues.append(
                    {
                        "issue": "missing_workflow_identity_index",
                        "table": f"{table_name}.{column_name}",
                        "count": 1,
                    }
                )
            if column_name not in foreign_key_columns:
                issues.append(
                    {
                        "issue": "missing_workflow_identity_foreign_key",
                        "table": f"{table_name}.{column_name}",
                        "count": 1,
                    }
                )
    with engine.connect() as connection:
        for table_name in CORE_TABLES:
            _append_count(
                issues,
                connection,
                "null_workflow_reference",
                table_name,
                f"SELECT COUNT(*) FROM {table_name} "
                "WHERE workflow_definition_id IS NULL OR current_state_id IS NULL",
            )
            _append_count(
                issues,
                connection,
                "invalid_current_state_definition",
                table_name,
                f"SELECT COUNT(*) FROM {table_name} item "
                "LEFT JOIN workflow_definitions definition ON definition.id = item.workflow_definition_id "
                "LEFT JOIN workflow_states state ON state.id = item.current_state_id "
                "WHERE definition.id IS NULL OR state.id IS NULL "
                "OR state.definition_id <> item.workflow_definition_id",
            )
        _append_count(
            issues,
            connection,
            "invalid_transition_definition",
            "workflow_transitions",
            "SELECT COUNT(*) FROM workflow_transitions transition_row "
            "LEFT JOIN workflow_states source ON source.id = transition_row.from_state_id "
            "LEFT JOIN workflow_states target ON target.id = transition_row.to_state_id "
            "WHERE transition_row.from_state_id IS NULL OR transition_row.to_state_id IS NULL "
            "OR source.id IS NULL OR target.id IS NULL "
            "OR source.definition_id <> transition_row.definition_id "
            "OR target.definition_id <> transition_row.definition_id",
        )
        _append_count(
            issues,
            connection,
            "invalid_initial_state_definition",
            "workflow_definitions",
            "SELECT COUNT(*) FROM workflow_definitions definition "
            "LEFT JOIN workflow_states state ON state.id = definition.initial_state_id "
            "WHERE definition.initial_state_id IS NOT NULL "
            "AND (state.id IS NULL OR state.definition_id <> definition.id OR state.enabled <> 1)",
        )
    return issues


def _append_count(issues, connection, issue: str, table_name: str, query: str) -> None:
    count = int(connection.execute(text(query)).scalar_one())
    if count:
        issues.append({"issue": issue, "table": table_name, "count": count})


def main() -> int:
    issues = collect_issues()
    print(json.dumps({"ok": not issues, "issues": issues}, ensure_ascii=False, indent=2))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
