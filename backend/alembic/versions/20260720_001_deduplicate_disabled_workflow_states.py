"""deduplicate disabled workflow states

Revision ID: 20260720_001
Revises: 20260717_002
Create Date: 2026-07-20 12:00:00.000000
"""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from copy import deepcopy
import json
import logging
from typing import Any, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260720_001"
down_revision: Union[str, None] = "20260717_002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

_DIRECT_REFERENCES = (
    ("requirements", "current_state_id"),
    ("tasks", "current_state_id"),
    ("bugs", "current_state_id"),
    ("projects", "current_state_id"),
    ("iterations", "current_state_id"),
    ("status_operation_logs", "from_state_id"),
    ("status_operation_logs", "to_state_id"),
    ("workflow_definitions", "initial_state_id"),
    ("workflow_transitions", "from_state_id"),
    ("workflow_transitions", "to_state_id"),
)


def _plan_duplicate_state_merges(states: Sequence[Mapping[str, Any]]) -> dict[int, int]:
    merges, _ = _plan_duplicate_state_merges_with_diagnostics(states)
    return merges


def _plan_duplicate_state_merges_with_diagnostics(
    states: Sequence[Mapping[str, Any]],
) -> tuple[dict[int, int], list[dict[str, Any]]]:
    grouped: dict[tuple[int, str], list[Mapping[str, Any]]] = defaultdict(list)
    for state in states:
        grouped[(int(state["definition_id"]), str(state["status_name"]))].append(state)

    merges: dict[int, int] = {}
    diagnostics: list[dict[str, Any]] = []
    for (definition_id, status_name), group in sorted(grouped.items()):
        enabled_ids = sorted(int(item["id"]) for item in group if bool(item["enabled"]))
        disabled_ids = sorted(int(item["id"]) for item in group if not bool(item["enabled"]))
        if not disabled_ids:
            continue
        if len(enabled_ids) == 1:
            merges.update({disabled_id: enabled_ids[0] for disabled_id in disabled_ids})
            continue
        diagnostics.append(
            {
                "definition_id": definition_id,
                "status_name": status_name,
                "disabled_ids": disabled_ids,
                "enabled_ids": enabled_ids,
                "reason": "no_enabled_match" if not enabled_ids else "ambiguous_enabled_match",
            }
        )
    return dict(sorted(merges.items())), diagnostics


def _json_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return deepcopy(dict(value))
    if isinstance(value, str):
        parsed = json.loads(value)
        return deepcopy(dict(parsed)) if isinstance(parsed, Mapping) else {}
    return {}


def _remap_condition_config(config: Any, merges: Mapping[int, int]) -> dict[str, Any]:
    remapped = _json_mapping(config)
    for field in ("routes", "target_state_id_by_owner"):
        values = remapped.get(field)
        if not isinstance(values, Mapping):
            continue
        remapped[field] = {
            key: _remap_state_id(value, merges)
            for key, value in values.items()
        }
    return remapped


def _remap_state_id(value: Any, merges: Mapping[int, int]) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return merges.get(value, value)
    if isinstance(value, str) and value.isdigit():
        return merges.get(int(value), value)
    return value


def _condition_references_state(config: Any, state_id: int) -> bool:
    parsed = _json_mapping(config)
    for field in ("routes", "target_state_id_by_owner"):
        values = parsed.get(field)
        if not isinstance(values, Mapping):
            continue
        for value in values.values():
            if value == state_id or (isinstance(value, str) and value.isdigit() and int(value) == state_id):
                return True
    return False


def _update_condition_configs(bind, merges: Mapping[int, int]) -> None:
    rows = bind.execute(
        sa.text(
            "SELECT id, condition_config FROM workflow_transitions "
            "WHERE condition_config IS NOT NULL ORDER BY id"
        )
    ).mappings()
    for row in rows:
        original = _json_mapping(row["condition_config"])
        remapped = _remap_condition_config(original, merges)
        if remapped == original:
            continue
        bind.execute(
            sa.text(
                "UPDATE workflow_transitions SET condition_config = :condition_config WHERE id = :id"
            ),
            {
                "condition_config": json.dumps(remapped, ensure_ascii=False, sort_keys=True),
                "id": int(row["id"]),
            },
        )


def _remaining_references(bind, state_id: int) -> list[str]:
    references: list[str] = []
    for table_name, column_name in _DIRECT_REFERENCES:
        count = bind.execute(
            sa.text(f"SELECT COUNT(*) FROM {table_name} WHERE {column_name} = :state_id"),
            {"state_id": state_id},
        ).scalar_one()
        if int(count):
            references.append(f"{table_name}.{column_name}")
    condition_rows = bind.execute(
        sa.text(
            "SELECT id, condition_config FROM workflow_transitions "
            "WHERE condition_config IS NOT NULL ORDER BY id"
        )
    ).mappings()
    if any(_condition_references_state(row["condition_config"], state_id) for row in condition_rows):
        references.append("workflow_transitions.condition_config")
    return references


def _execute_migration(bind) -> list[dict[str, Any]]:
    states = list(
        bind.execute(
            sa.text(
                "SELECT id, definition_id, status_name, enabled "
                "FROM workflow_states ORDER BY definition_id, status_name, id"
            )
        ).mappings()
    )
    merges, diagnostics = _plan_duplicate_state_merges_with_diagnostics(states)
    for diagnostic in diagnostics:
        logger.warning(
            "Skipping disabled workflow state merge: definition=%s status=%r disabled=%s enabled=%s reason=%s",
            diagnostic["definition_id"],
            diagnostic["status_name"],
            diagnostic["disabled_ids"],
            diagnostic["enabled_ids"],
            diagnostic["reason"],
        )

    for old_id, new_id in merges.items():
        for table_name, column_name in _DIRECT_REFERENCES:
            bind.execute(
                sa.text(
                    f"UPDATE {table_name} SET {column_name} = :new_id WHERE {column_name} = :old_id"
                ),
                {"new_id": new_id, "old_id": old_id},
            )
    _update_condition_configs(bind, merges)

    audit_failures = {
        old_id: references
        for old_id in merges
        if (references := _remaining_references(bind, old_id))
    }
    if audit_failures:
        details = "; ".join(
            f"{state_id}={','.join(references)}"
            for state_id, references in sorted(audit_failures.items())
        )
        raise RuntimeError(f"Disabled workflow state reference audit failed: {details}")

    for old_id in merges:
        bind.execute(
            sa.text("DELETE FROM workflow_states WHERE id = :old_id AND enabled = 0"),
            {"old_id": old_id},
        )
    return diagnostics


def upgrade() -> None:
    _execute_migration(op.get_bind())


def downgrade() -> None:
    # Removed duplicate identities and their original reference ownership cannot be reconstructed safely.
    pass
