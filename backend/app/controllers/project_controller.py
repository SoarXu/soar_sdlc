from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.project_service import (
    activate_project,
    close_project,
    create_project,
    delete_project,
    get_project,
    list_project_status_operations,
    list_projects,
    start_project,
    suspend_project,
    update_project,
)
from app.views.project_view import ProjectCreate, ProjectRead, ProjectUpdate
from app.views.status_operation_view import StatusOperationCreate, StatusOperationRead


router = APIRouter()


@router.get("", response_model=list[ProjectRead])
def get_projects(db: Session = Depends(get_db)):
    return list_projects(db)


@router.get("/{project_id}", response_model=ProjectRead)
def get_project_detail(project_id: int, db: Session = Depends(get_db)):
    return get_project(db, project_id)


@router.post("", response_model=ProjectRead)
def post_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    return create_project(db, payload)


@router.patch("/{project_id}", response_model=ProjectRead)
def patch_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)):
    return update_project(db, project_id, payload)


@router.get("/{project_id}/status-operations", response_model=list[StatusOperationRead])
def get_project_status_operations(project_id: int, db: Session = Depends(get_db)):
    return list_project_status_operations(db, project_id)


@router.post("/{project_id}/start", response_model=ProjectRead)
def start_project_status(project_id: int, payload: StatusOperationCreate | None = None, db: Session = Depends(get_db)):
    return start_project(db, project_id, payload)


@router.post("/{project_id}/suspend", response_model=ProjectRead)
def suspend_project_status(project_id: int, payload: StatusOperationCreate | None = None, db: Session = Depends(get_db)):
    return suspend_project(db, project_id, payload)


@router.post("/{project_id}/close", response_model=ProjectRead)
def close_project_status(project_id: int, payload: StatusOperationCreate | None = None, db: Session = Depends(get_db)):
    return close_project(db, project_id, payload)


@router.post("/{project_id}/activate", response_model=ProjectRead)
def activate_project_status(project_id: int, payload: StatusOperationCreate | None = None, db: Session = Depends(get_db)):
    return activate_project(db, project_id, payload)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_project(project_id: int, db: Session = Depends(get_db)):
    delete_project(db, project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
