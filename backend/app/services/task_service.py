from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.task import Task
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
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, task_id: int) -> None:
    task = _get_active_task(db, task_id)
    task.deleted = 1
    task.delete_time = datetime.now()
    db.commit()


def _get_active_task(db: Session, task_id: int) -> Task:
    task = db.query(Task).filter(Task.id == task_id, Task.deleted == 0).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task
