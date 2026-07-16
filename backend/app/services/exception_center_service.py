from datetime import datetime

from sqlalchemy.orm import Session

from app.models.bug import Bug
from app.models.requirement import Requirement
from app.models.status_operation import StatusOperationLog
from app.models.task import Task
from app.services.exception_rule_service import ensure_default_exception_rules, resolve_exception_rule


TERMINAL_STATUSES = {
    "requirement": {"completed", "canceled"},
    "task": {"completed", "canceled"},
    "bug": {"closed"},
}


def list_exception_refs(
    db: Session,
    scoped_project_ids: set[int] | None = None,
    *,
    now: datetime | None = None,
) -> list[dict]:
    ensure_default_exception_rules(db)
    evaluation_time = now or datetime.now()
    refs: list[dict] = []
    seen: set[tuple[str, int, str]] = set()

    def add_if_due(
        object_type: str,
        item,
        exception_key: str,
        entered_at: datetime | None,
        *,
        current_count: int | None = None,
    ) -> None:
        signature = (object_type, item.id, exception_key)
        if signature in seen:
            return
        rule = resolve_exception_rule(
            db,
            exception_key,
            object_type,
            item.project_id,
            str(getattr(item, "priority", None) or getattr(item, "severity", None) or "") or None,
            item.status,
        )
        if not rule:
            return
        if rule.threshold_count is not None and (current_count or 0) < rule.threshold_count:
            return
        elapsed_hours = _elapsed_hours(entered_at, evaluation_time)
        threshold_hours = rule.threshold_hours or 0
        if rule.threshold_hours is not None and elapsed_hours < threshold_hours:
            return
        seen.add(signature)
        refs.append(
            {
                "object_type": object_type,
                "id": item.id,
                "project_id": item.project_id,
                "priority": getattr(item, "priority", None) or getattr(item, "severity", None),
                "status": item.status,
                "owner_id": getattr(item, "owner_id", None),
                "handler_id": getattr(item, "owner_id", None),
                "exception_key": exception_key,
                "exception_label": rule.label,
                "entered_at": entered_at.isoformat() if entered_at else None,
                "threshold_hours": rule.threshold_hours,
                "threshold_count": rule.threshold_count,
                "overdue_hours": round(max(0.0, elapsed_hours - threshold_hours), 2),
            }
        )

    for requirement in db.query(Requirement).filter(Requirement.deleted == 0).all():
        if not _in_scope(requirement.project_id, scoped_project_ids):
            continue
        entered_at = _latest_state_time(db, "requirement", requirement.id, requirement.status, requirement.create_time)
        if requirement.owner_id is None and requirement.status not in TERMINAL_STATUSES["requirement"]:
            add_if_due("requirement", requirement, "unassigned_timeout", entered_at)
        elif requirement.owner_id and requirement.status not in TERMINAL_STATUSES["requirement"]:
            add_if_due("requirement", requirement, "pending_timeout", entered_at)
        if requirement.status == "completed":
            has_active_bug = db.query(Bug.id).filter(
                Bug.requirement_id == requirement.id,
                Bug.deleted == 0,
                Bug.status != "closed",
            ).first()
            if has_active_bug:
                add_if_due("requirement", requirement, "completed_requirement_active_bug", entered_at)

    for task in db.query(Task).filter(Task.deleted == 0).all():
        if not _in_scope(task.project_id, scoped_project_ids):
            continue
        entered_at = _latest_state_time(db, "task", task.id, task.status, task.create_time)
        if task.owner_id is None and task.status not in TERMINAL_STATUSES["task"]:
            add_if_due("task", task, "unassigned_timeout", entered_at)
        elif task.owner_id and task.status not in TERMINAL_STATUSES["task"]:
            add_if_due("task", task, "pending_timeout", entered_at)
        if task.status == "in_processing":
            add_if_due("task", task, "fixing_timeout", entered_at)
        if _is_high_priority(task.priority) and task.status not in TERMINAL_STATUSES["task"]:
            add_if_due("task", task, "high_priority_unprocessed", entered_at)

    for bug in db.query(Bug).filter(Bug.deleted == 0).all():
        if not _in_scope(bug.project_id, scoped_project_ids):
            continue
        entered_at = _latest_state_time(db, "bug", bug.id, bug.status, bug.create_time)
        if bug.owner_id is None and bug.status not in TERMINAL_STATUSES["bug"]:
            add_if_due("bug", bug, "unassigned_timeout", entered_at)
        elif bug.owner_id and bug.status not in TERMINAL_STATUSES["bug"]:
            add_if_due("bug", bug, "pending_timeout", entered_at)
        if bug.status == "fixing":
            add_if_due("bug", bug, "fixing_timeout", entered_at)
        if bug.status == "pending_verification":
            add_if_due("bug", bug, "pending_verification_timeout", entered_at)
        if bug.status == "verified":
            add_if_due("bug", bug, "verified_not_closed", entered_at)
        if bug.verify_result == "failed":
            failed_at = _latest_action_time(db, "bug", bug.id, "verification_failed", bug.verify_time or entered_at)
            add_if_due("bug", bug, "verification_failed", failed_at)
        if (bug.reopen_count or 0) > 0:
            activated_at = _latest_action_time(db, "bug", bug.id, "activate", entered_at)
            add_if_due("bug", bug, "repeated_activation", activated_at, current_count=bug.reopen_count)
        if _is_high_priority(bug.priority or bug.severity) and bug.status != "closed":
            add_if_due("bug", bug, "high_priority_unprocessed", entered_at)

    return refs


def _latest_state_time(
    db: Session,
    object_type: str,
    object_id: int,
    current_status: str,
    fallback: datetime | None,
) -> datetime | None:
    operation = db.query(StatusOperationLog).filter(
        StatusOperationLog.object_type == object_type,
        StatusOperationLog.object_id == object_id,
        StatusOperationLog.to_status == current_status,
    ).order_by(StatusOperationLog.effective_time.desc(), StatusOperationLog.id.desc()).first()
    return operation.effective_time if operation else fallback


def _latest_action_time(
    db: Session,
    object_type: str,
    object_id: int,
    action: str,
    fallback: datetime | None,
) -> datetime | None:
    operation = db.query(StatusOperationLog).filter(
        StatusOperationLog.object_type == object_type,
        StatusOperationLog.object_id == object_id,
        StatusOperationLog.action == action,
    ).order_by(StatusOperationLog.effective_time.desc(), StatusOperationLog.id.desc()).first()
    return operation.effective_time if operation else fallback


def _elapsed_hours(entered_at: datetime | None, now: datetime) -> float:
    if not entered_at:
        return 0.0
    evaluation_time = now
    if entered_at.tzinfo and not evaluation_time.tzinfo:
        evaluation_time = evaluation_time.replace(tzinfo=entered_at.tzinfo)
    elif evaluation_time.tzinfo and not entered_at.tzinfo:
        entered_at = entered_at.replace(tzinfo=evaluation_time.tzinfo)
    return max(0.0, (evaluation_time - entered_at).total_seconds() / 3600)


def _in_scope(project_id: int | None, scoped_project_ids: set[int] | None) -> bool:
    if not scoped_project_ids:
        return True
    return bool(project_id and project_id in scoped_project_ids)


def _is_high_priority(priority: str | None) -> bool:
    return str(priority or "").lower() in {"1", "high", "urgent"}
