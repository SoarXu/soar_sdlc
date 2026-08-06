"""backfill unallocated tasks and bugs into project work pools

Revision ID: 20260806_002
Revises: 20260806_001
Create Date: 2026-08-06 14:00:00.000000
"""

from collections.abc import Sequence
import json
from typing import Any, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260806_002"
down_revision: Union[str, None] = "20260806_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BACKFILL_REASON = "project_work_pool_backfill"


def _backfill_project_work_pool_items(bind) -> dict[str, Any]:
    metadata = sa.MetaData()
    projects = sa.Table("projects", metadata, autoload_with=bind)
    states = sa.Table("workflow_states", metadata, autoload_with=bind)
    history = sa.Table("work_item_iteration_history", metadata, autoload_with=bind)
    updated = {"task": 0, "bug": 0}

    for object_type, table_name in (("task", "tasks"), ("bug", "bugs")):
        items = sa.Table(table_name, metadata, autoload_with=bind)
        rows = bind.execute(
            sa.select(
                items.c.id,
                items.c.project_id,
                projects.c.requirement_pool_iteration_id.label("pool_id"),
            )
            .join(projects, projects.c.id == items.c.project_id)
            .join(states, states.c.id == items.c.current_state_id)
            .where(
                items.c.iteration_id.is_(None),
                items.c.deleted == 0,
                states.c.category != "terminal",
                projects.c.requirement_pool_iteration_id.is_not(None),
            )
            .order_by(items.c.id)
        ).mappings().all()
        for row in rows:
            result = bind.execute(
                items.update()
                .where(items.c.id == row["id"], items.c.iteration_id.is_(None))
                .values(iteration_id=row["pool_id"])
            )
            if result.rowcount != 1:
                continue
            updated[object_type] += 1
            open_history_id = bind.execute(
                sa.select(history.c.id).where(
                    history.c.object_type == object_type,
                    history.c.object_id == row["id"],
                    history.c.left_at.is_(None),
                )
            ).scalar_one_or_none()
            if open_history_id is None:
                bind.execute(
                    history.insert().values(
                        object_type=object_type,
                        object_id=row["id"],
                        iteration_id=row["pool_id"],
                        enter_reason=_BACKFILL_REASON,
                        migrated=1,
                    )
                )

    return {
        "updated": updated,
        "terminal_pool_anomalies": _terminal_pool_anomalies(bind),
    }


def _terminal_pool_anomalies(bind) -> list[dict[str, Any]]:
    metadata = sa.MetaData()
    projects = sa.Table("projects", metadata, autoload_with=bind)
    states = sa.Table("workflow_states", metadata, autoload_with=bind)
    anomalies = []
    for object_type, table_name in (
        ("bug", "bugs"),
        ("requirement", "requirements"),
        ("task", "tasks"),
    ):
        items = sa.Table(table_name, metadata, autoload_with=bind)
        rows = bind.execute(
            sa.select(
                items.c.id.label("object_id"),
                items.c.project_id,
                items.c.iteration_id,
            )
            .join(projects, projects.c.id == items.c.project_id)
            .join(states, states.c.id == items.c.current_state_id)
            .where(
                items.c.deleted == 0,
                items.c.iteration_id == projects.c.requirement_pool_iteration_id,
                states.c.category == "terminal",
            )
            .order_by(items.c.id)
        ).mappings().all()
        anomalies.extend(
            {
                "object_type": object_type,
                "object_id": int(row["object_id"]),
                "project_id": int(row["project_id"]),
                "iteration_id": int(row["iteration_id"]),
            }
            for row in rows
        )
    return sorted(anomalies, key=lambda row: (row["object_type"], row["object_id"]))


def upgrade() -> None:
    report = _backfill_project_work_pool_items(op.get_bind())
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


def downgrade() -> None:
    # Backfilled items may have moved since upgrade; reversing them would lose valid planning data.
    pass
