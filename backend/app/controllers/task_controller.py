from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.task_service import create_task, delete_task, get_task, list_tasks, update_task
from app.views.task_view import TaskCreate, TaskRead, TaskUpdate


router = APIRouter()


@router.get("", response_model=list[TaskRead])
def get_tasks(db: Session = Depends(get_db)):
    return list_tasks(db)


@router.get("/{task_id}", response_model=TaskRead)
def get_task_detail(task_id: int, db: Session = Depends(get_db)):
    return get_task(db, task_id)


@router.post("", response_model=TaskRead)
def post_task(payload: TaskCreate, db: Session = Depends(get_db)):
    return create_task(db, payload)


@router.patch("/{task_id}", response_model=TaskRead)
def patch_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)):
    return update_task(db, task_id, payload)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_task(task_id: int, db: Session = Depends(get_db)):
    delete_task(db, task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
