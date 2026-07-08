from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.bug import Bug
from app.models.handler_transition_rule import HandlerTransitionRule
from app.models.iteration import Iteration
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.task import Task
from app.models.user import User
from app.services.current_handler_service import ensure_assign_permission, ensure_project_member
from app.services.handler_transition_rule_service import _first_project_member_id, _split_csv
from app.services.status_operation_service import create_status_operation
from app.views.status_operation_view import StatusOperationCreate
from app.views.work_item_view import (
    WorkItemAssignRequest,
    WorkItemAssignResult,
    WorkItemAutoAssignRequest,
    WorkItemBatchAssignRequest,
    WorkItemBatchResult,
    WorkItemClaimRequest,
    WorkItemFailure,
    WorkItemListRead,
    WorkItemRead,
    WorkItemRef,
)


MODEL_BY_TYPE = {
    "requirement": Requirement,
    "task": Task,
    "bug": Bug,
}
TERMINAL_STATUSES = {
    "requirement": {"done", "closed"},
    "task": {"done", "closed"},
    "bug": {"closed"},
}
DEFAULT_OVERDUE_HOURS = {
    "1": 4,
    "2": 4,
    "3": 24,
    "4": 48,
    "5": 48,
    "high": 4,
    "medium": 24,
    "low": 48,
}


def list_unassigned_work_items(db: Session) -> WorkItemListRead:
    projects = _project_map(db)
    iterations = _iteration_map(db)
    items = []
    for object_type, model in MODEL_BY_TYPE.items():
        rows = (
            db.query(model)
            .filter(
                model.deleted == 0,
                model.owner_id.is_(None),
                model.status.notin_(TERMINAL_STATUSES[object_type]),
            )
            .all()
        )
        items.extend(_read_item(object_type, row, projects, iterations) for row in rows)
    items.sort(key=lambda item: (item.overdue is False, item.create_time or datetime.min, item.id))
    return WorkItemListRead(
        items=items,
        total=len(items),
        overdue_count=sum(1 for item in items if item.overdue),
    )


def claim_work_item(
    db: Session,
    object_type: str,
    object_id: int,
    payload: WorkItemClaimRequest,
    actor: User | None,
):
    if not actor:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    item = _get_item(db, object_type, object_id)
    _ensure_not_terminal(object_type, item)
    if item.owner_id is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Work item already assigned")
    ensure_project_member(db, item.project_id, actor.id)
    _set_owner(db, object_type, item, actor.id, actor, "claim", payload.remark)
    db.commit()
    db.refresh(item)
    return item


def assign_work_item(
    db: Session,
    object_type: str,
    object_id: int,
    payload: WorkItemAssignRequest,
    actor: User | None,
):
    item = _get_item(db, object_type, object_id)
    _ensure_not_terminal(object_type, item)
    ensure_assign_permission(db, item.project_id, actor)
    ensure_project_member(db, item.project_id, payload.owner_id)
    _set_owner(db, object_type, item, payload.owner_id, actor, "assign", payload.remark)
    db.commit()
    db.refresh(item)
    return item


def batch_assign_work_items(
    db: Session,
    payload: WorkItemBatchAssignRequest,
    actor: User | None,
) -> WorkItemBatchResult:
    successes: list[WorkItemAssignResult] = []
    failures: list[WorkItemFailure] = []
    for ref in payload.items:
        try:
            item = _get_item(db, ref.object_type, ref.id)
            _ensure_not_terminal(ref.object_type, item)
            ensure_assign_permission(db, item.project_id, actor)
            ensure_project_member(db, item.project_id, payload.owner_id)
            _set_owner(db, ref.object_type, item, payload.owner_id, actor, "assign", payload.remark)
            db.flush()
            successes.append(WorkItemAssignResult(object_type=ref.object_type, id=ref.id, owner_id=payload.owner_id))
        except HTTPException as exc:
            failures.append(WorkItemFailure(object_type=ref.object_type, id=ref.id, reason=str(exc.detail)))
    db.commit()
    return WorkItemBatchResult(success_items=successes, failures=failures)


def auto_assign_unassigned_work_items(
    db: Session,
    payload: WorkItemAutoAssignRequest,
    actor: User | None,
) -> WorkItemBatchResult:
    refs = payload.items or [
        WorkItemRef(object_type=item.object_type, id=item.id)
        for item in list_unassigned_work_items(db).items
    ]
    successes: list[WorkItemAssignResult] = []
    failures: list[WorkItemFailure] = []
    for ref in refs:
        try:
            item = _get_item(db, ref.object_type, ref.id)
            _ensure_not_terminal(ref.object_type, item)
            ensure_assign_permission(db, item.project_id, actor)
            owner_id = _auto_owner_id(db, ref.object_type, item)
            if not owner_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No auto assignment target found")
            ensure_project_member(db, item.project_id, owner_id)
            _set_owner(db, ref.object_type, item, owner_id, actor, "auto_assign", "auto assign from work item pool")
            db.flush()
            successes.append(WorkItemAssignResult(object_type=ref.object_type, id=ref.id, owner_id=owner_id))
        except HTTPException as exc:
            failures.append(WorkItemFailure(object_type=ref.object_type, id=ref.id, reason=str(exc.detail)))
    db.commit()
    return WorkItemBatchResult(success_items=successes, failures=failures)


def _get_item(db: Session, object_type: str, object_id: int):
    model = MODEL_BY_TYPE.get(object_type)
    if not model:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported work item type")
    item = db.query(model).filter(model.id == object_id, model.deleted == 0).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work item not found")
    return item


def _ensure_not_terminal(object_type: str, item) -> None:
    if item.status in TERMINAL_STATUSES[object_type]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Terminal work item cannot be assigned")


def _set_owner(
    db: Session,
    object_type: str,
    item,
    owner_id: int,
    actor: User | None,
    action: str,
    remark: str | None,
) -> None:
    previous_owner_id = item.owner_id
    item.owner_id = owner_id
    message = f"{action}: {previous_owner_id} -> {owner_id}"
    if remark:
        message = f"{message}. {remark}"
    create_status_operation(
        db,
        object_type=object_type,
        object_id=item.id,
        action=action,
        from_status=item.status,
        to_status=item.status,
        payload=StatusOperationCreate(remark=message),
        actor_id=actor.id if actor else None,
    )


def _auto_owner_id(db: Session, object_type: str, item) -> int | None:
    project = db.query(Project).filter(Project.id == item.project_id, Project.deleted == 0).first()
    if not project or not project.assignee_rule_config_id:
        return None
    rule = (
        db.query(HandlerTransitionRule)
        .filter(
            HandlerTransitionRule.config_id == project.assignee_rule_config_id,
            HandlerTransitionRule.rule_type == "advanced",
            HandlerTransitionRule.object_type == object_type,
            HandlerTransitionRule.from_status == item.status,
            HandlerTransitionRule.enabled == True,  # noqa: E712
        )
        .order_by(HandlerTransitionRule.id.asc())
        .first()
    )
    if not rule:
        return None
    if rule.target_type == "keep_current":
        return item.owner_id
    if rule.target_type == "none":
        return None
    if rule.target_type == "project_role":
        return _first_project_member_id(db, item.project_id, _split_csv(rule.target_roles))
    if rule.fallback_type == "project_role":
        return _first_project_member_id(db, item.project_id, _split_csv(rule.fallback_roles))
    return None


def _project_map(db: Session) -> dict[int, Project]:
    return {project.id: project for project in db.query(Project).filter(Project.deleted == 0).all()}


def _iteration_map(db: Session) -> dict[int, Iteration]:
    return {iteration.id: iteration for iteration in db.query(Iteration).filter(Iteration.deleted == 0).all()}


def _read_item(
    object_type: str,
    item,
    projects: dict[int, Project],
    iterations: dict[int, Iteration],
) -> WorkItemRead:
    waiting_hours = _waiting_hours(item.create_time)
    threshold = _overdue_threshold_hours(getattr(item, "priority", None) or getattr(item, "severity", None))
    return WorkItemRead(
        id=item.id,
        object_type=object_type,
        title=item.title,
        project_id=item.project_id,
        project_name=projects.get(item.project_id).name if item.project_id in projects else None,
        iteration_id=getattr(item, "iteration_id", None),
        iteration_name=iterations.get(item.iteration_id).name if getattr(item, "iteration_id", None) in iterations else None,
        status=item.status,
        priority=getattr(item, "priority", None),
        severity=getattr(item, "severity", None),
        owner_id=item.owner_id,
        create_time=item.create_time,
        waiting_hours=waiting_hours,
        overdue=waiting_hours >= threshold,
    )


def _waiting_hours(create_time: datetime | None) -> float:
    if not create_time:
        return 0
    now = datetime.now(tz=create_time.tzinfo) if create_time.tzinfo else datetime.now()
    return max(0, round((now - create_time).total_seconds() / 3600, 2))


def _overdue_threshold_hours(priority: str | None) -> int:
    return DEFAULT_OVERDUE_HOURS.get(str(priority or "3").lower(), 24)
