from datetime import date, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.project import Project
from app.models.task import Task
from app.services.status_operation_service import create_status_operation, list_status_operations
from app.views.status_operation_view import StatusOperationCreate
from app.views.task_view import TaskCreate, TaskUpdate


def list_tasks(db: Session) -> list[Task]:
    return db.query(Task).filter(Task.deleted == 0).order_by(Task.id.desc()).all()


def get_task(db: Session, task_id: int) -> Task:
    return _get_active_task(db, task_id)


def create_task(db: Session, payload: TaskCreate) -> Task:
    data = payload.model_dump()
    if data.get("source_project_id") and not data.get("owner_id"):
        source_project = db.query(Project).filter(Project.id == data["source_project_id"], Project.deleted == 0).first()
        if source_project and source_project.owner_id:
            data["owner_id"] = source_project.owner_id
    task = Task(**data)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_task(db: Session, task_id: int, payload: TaskUpdate) -> Task:
    task = _get_active_task(db, task_id)
    _ensure_project_editable_for_task(db, task)
    data = payload.model_dump(exclude_unset=True)
    before_data, after_data = _task_change_data(task, data)
    for field, value in data.items():
        setattr(task, field, value)
    if before_data:
        db.add(
            AuditLog(
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


def activate_task(db: Session, task_id: int) -> Task:
    task = _get_active_task(db, task_id)
    _ensure_project_open_for_task(db, task)
    from_status = task.status
    task.status = "doing"
    create_status_operation(
        db,
        object_type="task",
        object_id=task.id,
        action="activate",
        from_status=from_status,
        to_status=task.status,
        payload=None,
    )
    db.commit()
    db.refresh(task)
    return task


def close_task(db: Session, task_id: int, payload: StatusOperationCreate) -> Task:
    if not payload.reason:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="关闭原因必填")
    task = _get_active_task(db, task_id)
    close_task_record(db, task, payload)
    db.commit()
    db.refresh(task)
    return task


def close_task_record(db: Session, task: Task, payload: StatusOperationCreate) -> Task:
    if task.status == "closed":
        return task
    from_status = task.status
    task.status = "closed"
    create_status_operation(
        db,
        object_type="task",
        object_id=task.id,
        action="close",
        from_status=from_status,
        to_status=task.status,
        payload=payload,
    )
    return task


def list_task_status_operations(db: Session, task_id: int) -> list[dict]:
    _get_active_task(db, task_id)
    return list_status_operations(db, "task", task_id)


def list_task_audit_logs(db: Session, task_id: int) -> list[AuditLog]:
    _get_active_task(db, task_id)
    return (
        db.query(AuditLog)
        .filter(AuditLog.object_type == "task", AuditLog.object_id == task_id)
        .order_by(AuditLog.create_time.desc(), AuditLog.id.desc())
        .all()
    )


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
    return value


def _ensure_project_editable_for_task(db: Session, task: Task) -> None:
    project = db.query(Project).filter(Project.id == task.project_id, Project.deleted == 0).first()
    if project and project.status == "closed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="项目已关闭，任务不允许编辑或删除")


def _ensure_project_open_for_task(db: Session, task: Task) -> None:
    project = db.query(Project).filter(Project.id == task.project_id, Project.deleted == 0).first()
    if project and project.status == "closed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="项目已关闭，任务不允许激活")
