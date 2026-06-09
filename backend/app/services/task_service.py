from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.task import Task
from app.views.task_view import TaskCreate, TaskUpdate


def list_tasks(db: Session) -> list[Task]:
    return db.query(Task).filter(Task.delete_time.is_(None)).order_by(Task.id.desc()).all()


def create_task(db: Session, payload: TaskCreate) -> Task:
    task = Task(**payload.model_dump())
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
    task.delete_time = datetime.now()
    db.commit()


def _get_active_task(db: Session, task_id: int) -> Task:
    task = db.query(Task).filter(Task.id == task_id, Task.delete_time.is_(None)).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task
