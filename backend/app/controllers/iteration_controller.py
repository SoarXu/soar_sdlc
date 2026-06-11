from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.iteration_service import (
    available_requirements,
    available_tasks,
    create_iteration,
    delete_iteration,
    get_iteration_detail,
    link_requirements,
    link_tasks,
    list_iteration_status_operations,
    list_iterations,
    start_iteration,
    unlink_requirement,
    unlink_task,
    update_iteration,
)
from app.views.status_operation_view import StatusOperationCreate, StatusOperationRead
from app.views.iteration_view import IterationCreate, IterationRead, IterationUpdate, LinkRequirementsRequest, LinkTasksRequest


router = APIRouter()


@router.get("", response_model=list[IterationRead])
def get_iterations(project_id: int | None = None, db: Session = Depends(get_db)):
    return list_iterations(db, project_id)


@router.post("", response_model=IterationRead)
def post_iteration(payload: IterationCreate, db: Session = Depends(get_db)):
    return create_iteration(db, payload)


@router.patch("/{iteration_id}", response_model=IterationRead)
def patch_iteration(iteration_id: int, payload: IterationUpdate, db: Session = Depends(get_db)):
    return update_iteration(db, iteration_id, payload)


@router.get("/{iteration_id}/detail")
def get_iteration_detail_view(iteration_id: int, db: Session = Depends(get_db)):
    return get_iteration_detail(db, iteration_id)


@router.get("/{iteration_id}/status-operations", response_model=list[StatusOperationRead])
def get_iteration_status_operations(iteration_id: int, db: Session = Depends(get_db)):
    return list_iteration_status_operations(db, iteration_id)


@router.post("/{iteration_id}/start", response_model=IterationRead)
def start_iteration_status(iteration_id: int, payload: StatusOperationCreate | None = None, db: Session = Depends(get_db)):
    return start_iteration(db, iteration_id, payload)


@router.get("/{iteration_id}/available-requirements")
def get_available_requirements(iteration_id: int, db: Session = Depends(get_db)):
    return available_requirements(db, iteration_id)


@router.post("/{iteration_id}/requirements")
def post_iteration_requirements(iteration_id: int, payload: LinkRequirementsRequest, db: Session = Depends(get_db)):
    return link_requirements(db, iteration_id, payload.requirement_ids)


@router.delete("/{iteration_id}/requirements/{requirement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_iteration_requirement(iteration_id: int, requirement_id: int, db: Session = Depends(get_db)):
    unlink_requirement(db, iteration_id, requirement_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{iteration_id}/available-tasks")
def get_available_tasks(iteration_id: int, db: Session = Depends(get_db)):
    return available_tasks(db, iteration_id)


@router.post("/{iteration_id}/tasks")
def post_iteration_tasks(iteration_id: int, payload: LinkTasksRequest, db: Session = Depends(get_db)):
    return link_tasks(db, iteration_id, payload.task_ids)


@router.delete("/{iteration_id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_iteration_task(iteration_id: int, task_id: int, db: Session = Depends(get_db)):
    unlink_task(db, iteration_id, task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{iteration_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_iteration(iteration_id: int, db: Session = Depends(get_db)):
    delete_iteration(db, iteration_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
