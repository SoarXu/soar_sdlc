from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.requirement import Requirement
from app.models.task import Task
from app.services.status_operation_service import create_status_operation, list_status_operations
from app.services.task_service import close_task_record
from app.views.requirement_view import GenerateTaskRequest, RequirementCreate, RequirementUpdate
from app.views.status_operation_view import StatusOperationCreate


def list_requirements(db: Session) -> list[Requirement]:
    return db.query(Requirement).filter(Requirement.deleted == 0).order_by(Requirement.id.desc()).all()


def get_requirement(db: Session, requirement_id: int) -> Requirement:
    return _get_active_requirement(db, requirement_id)


def create_requirement(db: Session, payload: RequirementCreate) -> Requirement:
    data = payload.model_dump()
    data["status"] = "draft"
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
        if field == "status":
            continue
        setattr(requirement, field, value)
    db.commit()
    db.refresh(requirement)
    return requirement


def activate_requirement(db: Session, requirement_id: int) -> Requirement:
    requirement = _get_active_requirement(db, requirement_id)
    _ensure_project_open_for_requirement(db, requirement)
    from_status = requirement.status
    requirement.status = "active"
    (
        db.query(Task)
        .filter(Task.requirement_id == requirement.id, Task.deleted == 0, Task.status == "todo")
        .update({Task.status: "doing"}, synchronize_session=False)
    )
    create_status_operation(
        db,
        object_type="requirement",
        object_id=requirement.id,
        action="activate",
        from_status=from_status,
        to_status=requirement.status,
        payload=None,
    )
    db.commit()
    db.refresh(requirement)
    return requirement


def close_requirement(db: Session, requirement_id: int, payload: StatusOperationCreate) -> Requirement:
    if not payload.reason:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="关闭原因必填")
    requirement = _get_active_requirement(db, requirement_id)
    close_requirement_record(db, requirement, payload)
    db.commit()
    db.refresh(requirement)
    return requirement


def close_requirement_record(db: Session, requirement: Requirement, payload: StatusOperationCreate) -> Requirement:
    tasks = (
        db.query(Task)
        .filter(Task.requirement_id == requirement.id, Task.deleted == 0, Task.status != "closed")
        .all()
    )
    for task in tasks:
        close_task_record(db, task, payload)
    if requirement.status == "closed":
        return requirement
    from_status = requirement.status
    requirement.status = "closed"
    create_status_operation(
        db,
        object_type="requirement",
        object_id=requirement.id,
        action="close",
        from_status=from_status,
        to_status=requirement.status,
        payload=payload,
    )
    return requirement


def list_requirement_status_operations(db: Session, requirement_id: int) -> list[dict]:
    _get_active_requirement(db, requirement_id)
    return list_status_operations(db, "requirement", requirement_id)


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


def _ensure_project_open_for_requirement(db: Session, requirement: Requirement) -> None:
    project = db.query(Project).filter(Project.id == requirement.project_id, Project.deleted == 0).first()
    if project and project.status == "closed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="项目已关闭，需求不允许激活")
