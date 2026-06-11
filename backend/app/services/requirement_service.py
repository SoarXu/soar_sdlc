from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.requirement import Requirement
from app.models.task import Task
from app.views.requirement_view import GenerateTaskRequest, RequirementCreate, RequirementUpdate


def list_requirements(db: Session) -> list[Requirement]:
    return db.query(Requirement).filter(Requirement.deleted == 0).order_by(Requirement.id.desc()).all()


def create_requirement(db: Session, payload: RequirementCreate) -> Requirement:
    data = payload.model_dump()
    if data.get("source_project_id") and not data.get("owner_id"):
        source_project = db.query(Project).filter(Project.id == data["source_project_id"], Project.deleted == 0).first()
        if source_project and source_project.owner_id:
            data["owner_id"] = source_project.owner_id
    requirement = Requirement(**data)
    db.add(requirement)
    db.commit()
    db.refresh(requirement)
    return requirement


def update_requirement(db: Session, requirement_id: int, payload: RequirementUpdate) -> Requirement:
    requirement = _get_active_requirement(db, requirement_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(requirement, field, value)
    db.commit()
    db.refresh(requirement)
    return requirement


def delete_requirement(db: Session, requirement_id: int) -> None:
    requirement = _get_active_requirement(db, requirement_id)
    requirement.deleted = 1
    requirement.delete_time = datetime.now()
    db.commit()


def generate_task_from_requirement(db: Session, requirement_id: int, payload: GenerateTaskRequest) -> Task:
    requirement = _get_active_requirement(db, requirement_id)
    task = Task(
        project_id=requirement.project_id,
        source_project_id=requirement.source_project_id,
        requirement_id=requirement.id,
        title=payload.title or requirement.title,
        task_type=payload.task_type,
        priority=payload.priority or requirement.priority,
        owner_id=requirement.owner_id,
        due_date=payload.due_date,
        status="todo",
        description=payload.description,
        source_requirement_review_status=requirement.review_status,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def _get_active_requirement(db: Session, requirement_id: int) -> Requirement:
    requirement = (
        db.query(Requirement)
        .filter(Requirement.id == requirement_id, Requirement.deleted == 0)
        .first()
    )
    if not requirement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
    return requirement
