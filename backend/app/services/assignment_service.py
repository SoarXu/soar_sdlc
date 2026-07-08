from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.bug import Bug
from app.models.requirement import Requirement
from app.models.task import Task
from app.models.user import User
from app.services.current_handler_service import ensure_assign_permission, ensure_project_member
from app.services.status_operation_service import create_status_operation
from app.views.status_operation_view import AssignOwnerRequest, BatchAssignOwnerRead, BatchAssignOwnerRequest, StatusOperationCreate


TERMINAL_STATUSES = {
    "requirement": {"done", "closed"},
    "task": {"done", "closed"},
    "bug": {"closed"},
}


def assign_requirement_owner(db: Session, requirement_id: int, payload: AssignOwnerRequest, actor: User | None = None) -> Requirement:
    requirement = _get_item(db, Requirement, requirement_id, "Requirement not found")
    _assign_owner(db, "requirement", requirement, payload, actor)
    db.commit()
    db.refresh(requirement)
    return requirement


def assign_task_owner(db: Session, task_id: int, payload: AssignOwnerRequest, actor: User | None = None) -> Task:
    task = _get_item(db, Task, task_id, "Task not found")
    _assign_owner(db, "task", task, payload, actor)
    db.commit()
    db.refresh(task)
    return task


def assign_bug_owner(db: Session, bug_id: int, payload: AssignOwnerRequest, actor: User | None = None) -> Bug:
    bug = _get_item(db, Bug, bug_id, "Bug not found")
    _assign_owner(db, "bug", bug, payload, actor)
    db.commit()
    db.refresh(bug)
    return bug


def batch_assign_requirement_owner(db: Session, payload: BatchAssignOwnerRequest, actor: User | None = None) -> BatchAssignOwnerRead:
    return _batch_assign(db, Requirement, "requirement", payload, actor, "Requirement not found")


def batch_assign_task_owner(db: Session, payload: BatchAssignOwnerRequest, actor: User | None = None) -> BatchAssignOwnerRead:
    return _batch_assign(db, Task, "task", payload, actor, "Task not found")


def batch_assign_bug_owner(db: Session, payload: BatchAssignOwnerRequest, actor: User | None = None) -> BatchAssignOwnerRead:
    return _batch_assign(db, Bug, "bug", payload, actor, "Bug not found")


def _batch_assign(db: Session, model, object_type: str, payload: BatchAssignOwnerRequest, actor: User | None, not_found_message: str) -> BatchAssignOwnerRead:
    success_ids: list[int] = []
    failures: list[dict] = []
    for item_id in payload.ids:
        try:
            item = _get_item(db, model, item_id, not_found_message)
            _assign_owner(db, object_type, item, AssignOwnerRequest(owner_id=payload.owner_id, remark=payload.remark), actor)
            db.flush()
            success_ids.append(item_id)
        except HTTPException as exc:
            failures.append({"id": item_id, "reason": str(exc.detail)})
    db.commit()
    return BatchAssignOwnerRead(success_ids=success_ids, failures=failures)


def _assign_owner(db: Session, object_type: str, item, payload: AssignOwnerRequest, actor: User | None) -> None:
    if item.status in TERMINAL_STATUSES[object_type]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="已完成或已关闭的工作项不允许指派")
    ensure_assign_permission(db, item.project_id, actor)
    ensure_project_member(db, item.project_id, payload.owner_id)
    previous_owner_id = item.owner_id
    item.owner_id = payload.owner_id
    remark = f"assign owner: {previous_owner_id} -> {payload.owner_id}"
    if payload.remark:
        remark = f"{remark}. {payload.remark}"
    create_status_operation(
        db,
        object_type=object_type,
        object_id=item.id,
        action="assign",
        from_status=item.status,
        to_status=item.status,
        payload=StatusOperationCreate(remark=remark),
        actor_id=actor.id if actor else None,
    )


def _get_item(db: Session, model, item_id: int, not_found_message: str):
    item = db.query(model).filter(model.id == item_id, model.deleted == 0).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_message)
    return item
