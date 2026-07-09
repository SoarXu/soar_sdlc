from datetime import date, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.services.current_handler_service import ensure_work_item_action
from app.services.lifecycle_service import project_lifecycle_phase, requirement_lifecycle_phase
from app.services.status_operation_service import list_status_operations
from app.views.task_view import TaskCreate, TaskUpdate


def list_tasks(db: Session) -> list[Task]:
    return db.query(Task).filter(Task.deleted == 0).order_by(Task.id.desc()).all()


def get_task(db: Session, task_id: int) -> Task:
    return _get_active_task(db, task_id)


def create_task(db: Session, payload: TaskCreate) -> Task:
    data = payload.model_dump()
    data["lifecycle_phase"] = (
        requirement_lifecycle_phase(db, data.get("requirement_id"))
        or project_lifecycle_phase(db, data.get("project_id"))
    )
    if data.get("status") not in {"pending_assignment", "in_processing", "pending_confirmation", "completed", "canceled"}:
        data["status"] = _initial_task_status(data.get("owner_id"))
    task = Task(**data)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_task(db: Session, task_id: int, payload: TaskUpdate, actor_id: int | None = None) -> Task:
    task = _get_active_task(db, task_id)
    ensure_work_item_action(db, task, actor_id, "task")
    _ensure_project_editable_for_task(db, task)
    data = payload.model_dump(exclude_unset=True)
    before_data, after_data = _task_change_data(task, data)
    for field, value in data.items():
        setattr(task, field, value)
    if before_data:
        db.add(
            AuditLog(
                actor_id=actor_id,
                action="update",
                object_type="task",
                object_id=task.id,
                before_data=before_data,
                after_data=after_data,
            )
        )
    db.commit()
    db.refresh(task)
    return task


def list_task_status_operations(db: Session, task_id: int) -> list[dict]:
    _get_active_task(db, task_id)
    return list_status_operations(db, "task", task_id)


def list_task_audit_logs(db: Session, task_id: int) -> list[dict]:
    _get_active_task(db, task_id)
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.object_type == "task", AuditLog.object_id == task_id)
        .order_by(AuditLog.create_time.desc(), AuditLog.id.desc())
        .all()
    )
    return _audit_logs_with_actor_names(db, logs)


def delete_task(db: Session, task_id: int) -> None:
    task = _get_active_task(db, task_id)
    _ensure_project_editable_for_task(db, task)
    task.deleted = 1
    task.delete_time = datetime.now()
    db.commit()


def _get_active_task(db: Session, task_id: int) -> Task:
    task = db.query(Task).filter(Task.id == task_id, Task.deleted == 0).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


def _initial_task_status(owner_id: int | None) -> str:
    return "in_processing" if owner_id else "pending_assignment"


def _task_change_data(task: Task, data: dict) -> tuple[dict, dict]:
    before_data = {}
    after_data = {}
    for field, new_value in data.items():
        old_value = getattr(task, field)
        old_normalized = _audit_value(old_value)
        new_normalized = _audit_value(new_value)
        if old_normalized != new_normalized:
            before_data[field] = old_normalized
            after_data[field] = new_normalized
    return before_data, after_data


def _audit_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _audit_logs_with_actor_names(db: Session, logs: list[AuditLog]) -> list[dict]:
    actor_ids = {log.actor_id for log in logs if log.actor_id}
    users = {}
    if actor_ids:
        users = {user.id: user.full_name for user in db.query(User).filter(User.id.in_(actor_ids)).all()}
    return [
        {
            "id": log.id,
            "actor_id": log.actor_id,
            "actor_name": users.get(log.actor_id) if log.actor_id else None,
            "action": log.action,
            "object_type": log.object_type,
            "object_id": log.object_id,
            "before_data": log.before_data,
            "after_data": log.after_data,
            "ip_address": log.ip_address,
            "user_agent": log.user_agent,
            "create_time": log.create_time,
        }
        for log in logs
    ]


def _ensure_project_editable_for_task(db: Session, task: Task) -> None:
    project = db.query(Project).filter(Project.id == task.project_id, Project.deleted == 0).first()
    if project and project.status == "closed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project is closed")
