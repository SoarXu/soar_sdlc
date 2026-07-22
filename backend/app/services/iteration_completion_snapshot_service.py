from datetime import datetime

from sqlalchemy.orm import Session

from app.models.bug import Bug
from app.models.iteration import Iteration
from app.models.iteration_completion_snapshot import IterationCompletionSnapshot
from app.models.requirement import Requirement
from app.models.task import Task
from app.models.test_run import TestRun
from app.services.workflow_state_query_service import is_terminal_state


DIRECT_MODELS = {
    "requirement": Requirement,
    "task": Task,
    "bug": Bug,
    "test_run": TestRun,
}


def create_completion_snapshot(
    db: Session,
    iteration: Iteration,
    *,
    action: str,
    actor_id: int | None,
    operation_log_id: int,
    ended_at: datetime,
) -> IterationCompletionSnapshot:
    existing = (
        db.query(IterationCompletionSnapshot)
        .filter(IterationCompletionSnapshot.iteration_id == iteration.id)
        .with_for_update()
        .first()
    )
    if existing:
        return existing

    item_rows = {key: _direct_rows(db, model, iteration.id) for key, model in DIRECT_MODELS.items()}
    items = {key: [_item_snapshot(item) for item in rows] for key, rows in item_rows.items()}
    counts = {key: len(rows) for key, rows in item_rows.items()}
    terminal_counts = {
        key: sum(_is_terminal(key, item) for item in rows)
        for key, rows in item_rows.items()
    }
    snapshot = IterationCompletionSnapshot(
        iteration_id=iteration.id,
        action=action,
        ended_at=ended_at,
        actor_id=actor_id,
        operation_log_id=operation_log_id,
        iteration_snapshot={
            "id": iteration.id,
            "name": iteration.name,
            "state_id": iteration.current_state_id,
            "status_name": iteration.status_name,
            "owner_id": iteration.owner_id,
        },
        counts=counts,
        terminal_counts=terminal_counts,
        items=items,
        gate_result={"passed": True, "blocker_counts": {key: 0 for key in DIRECT_MODELS}},
    )
    db.add(snapshot)
    return snapshot


def get_completion_snapshot(db: Session, iteration_id: int) -> dict | None:
    snapshot = (
        db.query(IterationCompletionSnapshot)
        .filter(IterationCompletionSnapshot.iteration_id == iteration_id)
        .first()
    )
    if not snapshot:
        return None
    return {
        "action": snapshot.action,
        "ended_at": snapshot.ended_at,
        "actor_id": snapshot.actor_id,
        "operation_log_id": snapshot.operation_log_id,
        "iteration": snapshot.iteration_snapshot,
        "counts": snapshot.counts,
        "terminal_counts": snapshot.terminal_counts,
        "items": snapshot.items,
        "gate_result": snapshot.gate_result,
    }


def _direct_rows(db: Session, model, iteration_id: int) -> list:
    return (
        db.query(model)
        .filter(model.iteration_id == iteration_id, model.deleted == 0)
        .order_by(model.id.asc())
        .with_for_update()
        .all()
    )


def _item_snapshot(item) -> dict:
    return {
        "id": item.id,
        "title": getattr(item, "title", None) or getattr(item, "name", None),
        "state_id": getattr(item, "current_state_id", None),
        "status_name": getattr(item, "status_name", None) or getattr(item, "status", None),
        "owner_id": getattr(item, "owner_id", None) or getattr(item, "test_owner_id", None),
    }


def _is_terminal(object_type: str, item) -> bool:
    return item.status in {"finished", "completed", "canceled", "closed"} if object_type == "test_run" else is_terminal_state(item)
