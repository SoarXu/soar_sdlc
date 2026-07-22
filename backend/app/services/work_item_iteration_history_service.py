from datetime import datetime

from sqlalchemy.orm import Session

from app.models.bug import Bug
from app.models.iteration import Iteration
from app.models.requirement import Requirement
from app.models.task import Task
from app.models.work_item_iteration_history import WorkItemIterationHistory


OBJECT_TYPE_BY_MODEL = {
    Requirement: "requirement",
    Task: "task",
    Bug: "bug",
}


def move_work_item_to_iteration(
    db: Session,
    item,
    target_iteration_id: int | None,
    *,
    actor_id: int | None = None,
    reason: str,
    operation_log_id: int | None = None,
    record_same_iteration_transition: bool = False,
) -> None:
    object_type = OBJECT_TYPE_BY_MODEL[type(item)]
    db.refresh(item, with_for_update=True)
    current_iteration_id = getattr(item, "iteration_id", None)
    open_rows = (
        db.query(WorkItemIterationHistory)
        .filter(
            WorkItemIterationHistory.object_type == object_type,
            WorkItemIterationHistory.object_id == item.id,
            WorkItemIterationHistory.left_at.is_(None),
        )
        .with_for_update()
        .all()
    )
    if current_iteration_id == target_iteration_id:
        if target_iteration_id and not any(row.iteration_id == target_iteration_id for row in open_rows):
            _open_history(db, object_type, item.id, target_iteration_id, actor_id, reason, operation_log_id)
            return
        if not target_iteration_id or not record_same_iteration_transition:
            return

    now = datetime.now()
    for row in open_rows:
        row.left_at = now
        row.left_by = actor_id
        row.leave_reason = reason
        row.title_snapshot = getattr(item, "title", None)
        row.state_id_snapshot = getattr(item, "current_state_id", None)
        row.status_name_snapshot = getattr(item, "status_name", None)
        row.owner_id_snapshot = getattr(item, "owner_id", None)
        row.operation_log_id = operation_log_id or row.operation_log_id

    item.iteration_id = target_iteration_id
    if target_iteration_id:
        _open_history(db, object_type, item.id, target_iteration_id, actor_id, reason, operation_log_id)


def list_iteration_history(db: Session, object_type: str, object_id: int) -> list[dict]:
    rows = (
        db.query(WorkItemIterationHistory)
        .filter(
            WorkItemIterationHistory.object_type == object_type,
            WorkItemIterationHistory.object_id == object_id,
        )
        .order_by(WorkItemIterationHistory.entered_at.asc(), WorkItemIterationHistory.id.asc())
        .all()
    )
    iteration_ids = {row.iteration_id for row in rows}
    names = {
        iteration.id: iteration.name
        for iteration in db.query(Iteration).filter(Iteration.id.in_(iteration_ids)).all()
    } if iteration_ids else {}
    return [
        {
            "iteration_id": row.iteration_id,
            "iteration_name": names.get(row.iteration_id),
            "entered_at": row.entered_at,
            "enter_reason": row.enter_reason,
            "left_at": row.left_at,
            "leave_reason": row.leave_reason,
            "status_name_at_leave": row.status_name_snapshot,
            "owner_id_at_leave": row.owner_id_snapshot,
        }
        for row in rows
    ]


def _open_history(
    db: Session,
    object_type: str,
    object_id: int,
    iteration_id: int,
    actor_id: int | None,
    reason: str,
    operation_log_id: int | None,
) -> None:
    db.add(
        WorkItemIterationHistory(
            object_type=object_type,
            object_id=object_id,
            iteration_id=iteration_id,
            entered_by=actor_id,
            enter_reason=reason,
            operation_log_id=operation_log_id,
        )
    )
