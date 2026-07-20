"""normalize workflow transition button configuration

Revision ID: 20260720_002
Revises: 20260720_001
Create Date: 2026-07-20 12:00:00.000000
"""

from collections.abc import Mapping, Sequence
import json
from typing import Any, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260720_002"
down_revision: Union[str, None] = "20260720_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OBSOLETE_KEYS = {"hidden", "list_priority", "visible_in_detail", "visible_in_list"}
_PROJECT_EFFECTIVE_TIME_FORMS = {
    "start": {"fields": [{"field": "effective_time", "label": "实际开始日期", "type": "date", "required": True}]},
    "close": {"fields": [{"field": "effective_time", "label": "实际完成日期", "type": "date", "required": True}]},
}


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str) and value:
        parsed = json.loads(value)
        return dict(parsed) if isinstance(parsed, Mapping) else {}
    return {}


def _number(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalization_updates(rows: Sequence[Mapping[str, Any]]) -> dict[int, dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for row in rows:
        config = _mapping(row.get("ui_config"))
        hidden = config.get("hidden") is True or config.get("list_display") == "hidden"
        group = config.get("list_display")
        if group not in {"primary", "more"}:
            group = "more"
        priority = _number(config.get("list_priority"), _number(row.get("sort_order"), 100))
        normalized_config = {key: value for key, value in config.items() if key not in _OBSOLETE_KEYS}
        normalized_config["list_display"] = group
        form_config = _mapping(row.get("form_config"))
        if row.get("object_type") == "project" and row.get("action_key") in _PROJECT_EFFECTIVE_TIME_FORMS:
            form_config = _PROJECT_EFFECTIVE_TIME_FORMS[str(row["action_key"])]
        prepared.append(
            {
                "id": int(row["id"]),
                "definition_id": int(row["definition_id"]),
                "from_state_id": int(row["from_state_id"]),
                "enabled": False if hidden else bool(row.get("enabled")),
                "group": group,
                "priority": priority,
                "old_order": _number(row.get("sort_order"), 100),
                "ui_config": normalized_config,
                "form_config": form_config or None,
            }
        )

    updates: dict[int, dict[str, Any]] = {}
    scopes = {(item["definition_id"], item["from_state_id"], item["group"]) for item in prepared}
    for scope in sorted(scopes):
        group_rows = [
            item
            for item in prepared
            if (item["definition_id"], item["from_state_id"], item["group"]) == scope
        ]
        group_rows.sort(key=lambda item: (item["priority"], item["old_order"], item["id"]))
        for index, item in enumerate(group_rows, start=1):
            updates[item["id"]] = {
                "enabled": item["enabled"],
                "sort_order": index * 10,
                "ui_config": item["ui_config"],
                "form_config": item["form_config"],
            }
    return updates


def upgrade() -> None:
    bind = op.get_bind()
    rows = list(
        bind.execute(
            sa.text(
                "SELECT wt.id, wt.definition_id, wd.object_type, wt.action_key, wt.from_state_id, "
                "wt.enabled, wt.sort_order, wt.ui_config, wt.form_config "
                "FROM workflow_transitions wt "
                "JOIN workflow_definitions wd ON wd.id = wt.definition_id "
                "ORDER BY wt.id"
            )
        ).mappings()
    )
    statement = sa.text(
        "UPDATE workflow_transitions SET enabled = :enabled, sort_order = :sort_order, "
        "ui_config = :ui_config, form_config = :form_config WHERE id = :transition_id"
    )
    for transition_id, update in sorted(_normalization_updates(rows).items()):
        bind.execute(
            statement,
            {
                "transition_id": transition_id,
                "enabled": 1 if update["enabled"] else 0,
                "sort_order": update["sort_order"],
                "ui_config": json.dumps(update["ui_config"], ensure_ascii=False, sort_keys=True),
                "form_config": (
                    json.dumps(update["form_config"], ensure_ascii=False, sort_keys=True)
                    if update["form_config"]
                    else None
                ),
            },
        )


def downgrade() -> None:
    # Removed visibility metadata cannot be reconstructed without inventing prior values.
    pass
