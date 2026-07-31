"""rename the project start action to launch

Revision ID: 20260731_001
Revises: 20260730_002
Create Date: 2026-07-31 10:00:00.000000
"""

from collections.abc import Mapping, Sequence
import json
from typing import Any, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260731_001"
down_revision: Union[str, None] = "20260730_002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str) and value:
        parsed = json.loads(value)
        return dict(parsed) if isinstance(parsed, Mapping) else {}
    return {}


def _project_start_label_updates(rows: Sequence[Mapping[str, Any]]) -> dict[int, dict[str, Any]]:
    updates: dict[int, dict[str, Any]] = {}
    for row in rows:
        config = _mapping(row.get("form_config"))
        config["title"] = "启动"
        config["submit_text"] = "启动"
        updates[int(row["id"])] = config
    return updates


def upgrade() -> None:
    bind = op.get_bind()
    rows = list(
        bind.execute(
            sa.text(
                "SELECT wt.id, wt.form_config "
                "FROM workflow_transitions wt "
                "JOIN workflow_definitions wd ON wd.id = wt.definition_id "
                "WHERE wd.object_type = 'project' AND wt.action_key = 'start'"
            )
        ).mappings()
    )
    statement = sa.text(
        "UPDATE workflow_transitions "
        "SET action_name = :action_name, form_config = :form_config "
        "WHERE id = :transition_id"
    )
    for transition_id, config in sorted(_project_start_label_updates(rows).items()):
        bind.execute(
            statement,
            {
                "transition_id": transition_id,
                "action_name": "启动",
                "form_config": json.dumps(config, ensure_ascii=False, sort_keys=True),
            },
        )


def downgrade() -> None:
    # The previous wording cannot be distinguished from a user-customized label.
    pass
