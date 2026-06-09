from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.project_service import create_project, delete_project, get_project, list_projects, update_project
from app.views.project_view import ProjectCreate, ProjectRead, ProjectUpdate


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


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_project(project_id: int, db: Session = Depends(get_db)):
    delete_project(db, project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
