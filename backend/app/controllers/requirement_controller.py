from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.requirement_service import (
    activate_requirement,
    create_requirement,
    delete_requirement,
    generate_task_from_requirement,
    get_requirement,
    list_requirements,
    update_requirement,
)
from app.views.requirement_view import GenerateTaskRequest, RequirementCreate, RequirementRead, RequirementUpdate
from app.views.task_view import TaskRead


router = APIRouter()


@router.get("", response_model=list[RequirementRead])
def get_requirements(db: Session = Depends(get_db)):
    return list_requirements(db)


@router.get("/{requirement_id}", response_model=RequirementRead)
def get_requirement_detail(requirement_id: int, db: Session = Depends(get_db)):
    return get_requirement(db, requirement_id)


@router.post("", response_model=RequirementRead)
def post_requirement(payload: RequirementCreate, db: Session = Depends(get_db)):
    return create_requirement(db, payload)


@router.patch("/{requirement_id}", response_model=RequirementRead)
def patch_requirement(requirement_id: int, payload: RequirementUpdate, db: Session = Depends(get_db)):
    return update_requirement(db, requirement_id, payload)


@router.post("/{requirement_id}/activate", response_model=RequirementRead)
def activate_requirement_status(requirement_id: int, db: Session = Depends(get_db)):
    return activate_requirement(db, requirement_id)


@router.delete("/{requirement_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_requirement(requirement_id: int, db: Session = Depends(get_db)):
    delete_requirement(db, requirement_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{requirement_id}/generate-task", response_model=TaskRead)
def generate_task(requirement_id: int, payload: GenerateTaskRequest, db: Session = Depends(get_db)):
    return generate_task_from_requirement(db, requirement_id, payload)
