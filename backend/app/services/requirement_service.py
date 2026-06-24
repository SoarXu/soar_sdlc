from datetime import date, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.task import Task
from app.services.lifecycle_service import project_lifecycle_phase
from app.services.project_team_service import default_requirement_owner_id
from app.services.status_operation_service import create_status_operation, list_status_operations
from app.services.task_service import close_task_record
from app.services.workflow_engine import execute_workflows
from app.views.requirement_view import GenerateTaskRequest, RequirementCreate, RequirementUpdate
from app.views.status_operation_view import StatusOperationCreate


def list_requirements(db: Session) -> list[Requirement]:
    return db.query(Requirement).filter(Requirement.deleted == 0).order_by(Requirement.id.desc()).all()


def get_requirement(db: Session, requirement_id: int) -> Requirement:
    return _get_active_requirement(db, requirement_id)


def create_requirement(db: Session, payload: RequirementCreate) -> Requirement:
    data = payload.model_dump()
    data["status"] = "draft"
    data["lifecycle_phase"] = project_lifecycle_phase(db, data.get("project_id"))
    if not data.get("owner_id"):
        data["owner_id"] = default_requirement_owner_id(db, data.get("source_project_id") or data.get("project_id"))
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
    _ensure_project_editable_for_requirement(db, requirement)
    data = payload.model_dump(exclude_unset=True)
    data.pop("status", None)
    before_data, after_data = _requirement_change_data(requirement, data)
    for field, value in data.items():
        setattr(requirement, field, value)
    if before_data:
        db.add(
            AuditLog(
                action="update",
                object_type="requirement",
                object_id=requirement.id,
                before_data=before_data,
                after_data=after_data,
            )
        )
    db.commit()
    db.refresh(requirement)
    return requirement


def activate_requirement(db: Session, requirement_id: int, actor_id: int | None = None) -> Requirement:
    requirement = _get_active_requirement(db, requirement_id)
    _ensure_project_open_for_requirement(db, requirement)
    from_status = requirement.status
    requirement.status = "active"
    linked_tasks = (
        db.query(Task)
        .filter(Task.requirement_id == requirement.id, Task.deleted == 0, Task.status != "closed")
        .all()
    )
    for task in linked_tasks:
        if task.status == "doing":
            continue
        task_from_status = task.status
        task.status = "doing"
        create_status_operation(
            db,
            object_type="task",
            object_id=task.id,
            action="activate",
            from_status=task_from_status,
            to_status=task.status,
            payload=None,
            actor_id=actor_id,
        )
    create_status_operation(
        db,
        object_type="requirement",
        object_id=requirement.id,
        action="activate",
        from_status=from_status,
        to_status=requirement.status,
        payload=None,
        actor_id=actor_id,
    )
    execute_workflows(
        db,
        target_object="requirement",
        trigger_action="status_changed",
        context={
            "target_object": "requirement",
            "object_id": requirement.id,
            "from_status": from_status,
            "to_status": requirement.status,
            "current_status": requirement.status,
        },
    )
    db.commit()
    db.refresh(requirement)
    return requirement


def close_requirement(db: Session, requirement_id: int, payload: StatusOperationCreate, actor_id: int | None = None) -> Requirement:
    if not payload.reason:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="关闭原因必填")
    requirement = _get_active_requirement(db, requirement_id)
    close_requirement_record(db, requirement, payload, actor_id=actor_id)
    db.commit()
    db.refresh(requirement)
    return requirement


def complete_requirement(db: Session, requirement_id: int, actor_id: int | None = None) -> Requirement:
    requirement = _get_active_requirement(db, requirement_id)
    _ensure_project_open_for_requirement(db, requirement)
    open_tasks = (
        db.query(Task)
        .filter(Task.requirement_id == requirement.id, Task.deleted == 0, Task.status.notin_(["done", "closed"]))
        .count()
    )
    if open_tasks:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="存在关联任务未完成，需求不允许完成")
    if requirement.status == "done":
        return requirement
    from_status = requirement.status
    requirement.status = "done"
    create_status_operation(
        db,
        object_type="requirement",
        object_id=requirement.id,
        action="complete",
        from_status=from_status,
        to_status=requirement.status,
        payload=None,
        actor_id=actor_id,
    )
    db.commit()
    db.refresh(requirement)
    return requirement


def close_requirement_record(
    db: Session,
    requirement: Requirement,
    payload: StatusOperationCreate,
    actor_id: int | None = None,
) -> Requirement:
    tasks = (
        db.query(Task)
        .filter(Task.requirement_id == requirement.id, Task.deleted == 0, Task.status != "closed")
        .all()
    )
    for task in tasks:
        close_task_record(db, task, payload, actor_id=actor_id)
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
        actor_id=actor_id,
    )
    return requirement


def list_requirement_status_operations(db: Session, requirement_id: int) -> list[dict]:
    _get_active_requirement(db, requirement_id)
    return list_status_operations(db, "requirement", requirement_id)


def list_requirement_audit_logs(db: Session, requirement_id: int) -> list[AuditLog]:
    _get_active_requirement(db, requirement_id)
    return (
        db.query(AuditLog)
        .filter(AuditLog.object_type == "requirement", AuditLog.object_id == requirement_id)
        .order_by(AuditLog.create_time.desc(), AuditLog.id.desc())
        .all()
    )


def delete_requirement(db: Session, requirement_id: int) -> None:
    requirement = _get_active_requirement(db, requirement_id)
    _ensure_project_editable_for_requirement(db, requirement)
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
        owner_id=payload.owner_id or requirement.owner_id,
        due_date=payload.due_date,
        status="todo",
        lifecycle_phase=requirement.lifecycle_phase,
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


def _ensure_project_editable_for_requirement(db: Session, requirement: Requirement) -> None:
    project = db.query(Project).filter(Project.id == requirement.project_id, Project.deleted == 0).first()
    if project and project.status == "closed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="项目已关闭，需求不允许编辑或删除")


def _requirement_change_data(requirement: Requirement, data: dict) -> tuple[dict, dict]:
    before_data = {}
    after_data = {}
    for field, new_value in data.items():
        old_value = getattr(requirement, field)
        old_normalized = _audit_value(old_value)
        new_normalized = _audit_value(new_value)
        if old_normalized != new_normalized:
            before_data[field] = old_normalized
            after_data[field] = new_normalized
    return before_data, after_data


def _audit_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value
