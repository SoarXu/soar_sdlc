from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.project_service import create_project, list_projects
from app.views.project_view import ProjectCreate, ProjectRead


router = APIRouter()


@router.get("", response_model=list[ProjectRead])
def get_projects(db: Session = Depends(get_db)):
    return list_projects(db)


@router.post("", response_model=ProjectRead)
def post_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    return create_project(db, payload)
