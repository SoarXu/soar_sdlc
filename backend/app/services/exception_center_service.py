from datetime import datetime

from sqlalchemy.orm import Session

from app.models.bug import Bug
from app.models.requirement import Requirement
from app.models.task import Task


TERMINAL_STATUSES = {
    "requirement": {"completed", "canceled", "done", "closed"},
    "task": {"completed", "canceled", "done", "closed"},
    "bug": {"closed"},
}

OVERDUE_HOURS_BY_PRIORITY = {
    "1": 4,
    "2": 4,
    "3": 24,
    "4": 48,
    "5": 48,
    "high": 4,
    "medium": 24,
    "low": 48,
}


def list_exception_refs(db: Session, scoped_project_ids: set[int] | None = None) -> list[dict]:
    refs: list[dict] = []
    seen: set[tuple[str, int, str]] = set()

    def add(object_type: str, object_id: int, exception_key: str, exception_label: str) -> None:
        signature = (object_type, object_id, exception_key)
        if signature in seen:
            return
        seen.add(signature)
        refs.append(
            {
                "object_type": object_type,
                "id": object_id,
                "exception_key": exception_key,
                "exception_label": exception_label,
            }
        )

    for requirement in db.query(Requirement).filter(Requirement.deleted == 0).all():
        if not _in_scope(requirement.project_id, scoped_project_ids):
            continue
        if requirement.owner_id is None and _is_overdue(requirement.create_time, requirement.priority):
            add("requirement", requirement.id, "unassigned_timeout", "未分派超时")
        elif requirement.owner_id and requirement.status not in TERMINAL_STATUSES["requirement"] and _is_overdue(
            requirement.create_time, requirement.priority
        ):
            add("requirement", requirement.id, "pending_timeout", "待处理超时")

    for task in db.query(Task).filter(Task.deleted == 0).all():
        if not _in_scope(task.project_id, scoped_project_ids):
            continue
        if task.owner_id is None and _is_overdue(task.create_time, task.priority):
            add("task", task.id, "unassigned_timeout", "未分派超时")
        elif task.owner_id and task.status not in TERMINAL_STATUSES["task"] and _is_overdue(task.create_time, task.priority):
            add("task", task.id, "pending_timeout", "待处理超时")

    for bug in db.query(Bug).filter(Bug.deleted == 0).all():
        if not _in_scope(bug.project_id, scoped_project_ids):
            continue
        if bug.status == "verified":
            add("bug", bug.id, "verified_not_closed", "已验证未关闭")
        if (bug.reopen_count or 0) >= 2:
            add("bug", bug.id, "repeated_activation", "重复激活")
        if bug.verify_result == "failed":
            add("bug", bug.id, "verification_failed", "验证失败")
        if bug.owner_id is None and _is_overdue(bug.create_time, bug.priority or bug.severity):
            add("bug", bug.id, "unassigned_timeout", "未分派超时")
        elif bug.owner_id and bug.status != "closed" and _is_overdue(bug.create_time, bug.priority or bug.severity):
            add("bug", bug.id, "pending_timeout", "待处理超时")
        if bug.owner_id is None and str(bug.priority or bug.severity or "").lower() in {"1", "high"}:
            add("bug", bug.id, "high_priority_unprocessed", "高优先级未处理")

    return refs


def _in_scope(project_id: int | None, scoped_project_ids: set[int] | None) -> bool:
    if not scoped_project_ids:
        return True
    return bool(project_id and project_id in scoped_project_ids)


def _is_overdue(create_time: datetime | None, priority: str | None) -> bool:
    if not create_time:
        return False
    threshold_hours = OVERDUE_HOURS_BY_PRIORITY.get(str(priority or "3").lower(), 24)
    now = datetime.now(tz=create_time.tzinfo) if create_time.tzinfo else datetime.now()
    waited_hours = (now - create_time).total_seconds() / 3600
    return waited_hours >= threshold_hours
