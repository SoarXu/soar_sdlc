from datetime import date, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.iteration import Iteration, IterationProject
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.task import Task
from app.models.test_case import TestCase
from app.models.user import User
from app.services.current_handler_service import ensure_work_item_action
from app.services.lifecycle_service import project_lifecycle_phase
from app.services.status_operation_service import list_status_operations
from app.services.workflow_runtime_service import execute_transition
from app.views.requirement_view import GenerateTaskRequest, RequirementCreate, RequirementUpdate
from app.views.status_operation_view import StatusOperationCreate
from app.views.workflow_runtime_view import WorkflowTransitionExecuteRequest


def list_requirements(db: Session) -> list[Requirement]:
    return db.query(Requirement).filter(Requirement.deleted == 0).order_by(Requirement.id.desc()).all()


def get_requirement(db: Session, requirement_id: int) -> Requirement:
    return _get_active_requirement(db, requirement_id)


def create_requirement(db: Session, payload: RequirementCreate) -> Requirement:
    data = payload.model_dump()
    _ensure_requirement_iteration_scope(db, data.get("project_id"), data.get("iteration_id"))
    if data.get("status") not in {"pending_assignment", "in_processing", "pending_confirmation", "completed", "canceled"}:
        data["status"] = _initial_requirement_status(data.get("owner_id"))
    data["lifecycle_phase"] = project_lifecycle_phase(db, data.get("project_id"))
    requirement = Requirement(**data)
    db.add(requirement)
    db.commit()
    db.refresh(requirement)
    return requirement


def update_requirement(db: Session, requirement_id: int, payload: RequirementUpdate, actor_id: int | None = None) -> Requirement:
    requirement = _get_active_requirement(db, requirement_id)
    ensure_work_item_action(db, requirement, actor_id, "需求")
    _ensure_project_editable_for_requirement(db, requirement)
    data = payload.model_dump(exclude_unset=True)
    data.pop("status", None)
    target_project_id = data.get("project_id", requirement.project_id)
    target_iteration_id = data.get("iteration_id", requirement.iteration_id)
    _ensure_requirement_iteration_scope(db, target_project_id, target_iteration_id)
    before_data, after_data = _requirement_change_data(requirement, data)
    for field, value in data.items():
        setattr(requirement, field, value)
    if before_data:
        db.add(
            AuditLog(
                actor_id=actor_id,
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
    ensure_work_item_action(db, requirement, actor_id, "需求")
    _ensure_project_open_for_requirement(db, requirement)
    if requirement.status in {"completed", "done"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Completed requirement cannot be activated")
    if requirement.status in {"canceled", "closed"}:
        return _run_requirement_transition(db, requirement, "reactivate", actor_id=actor_id)
    if requirement.status in {"pending_assignment", "draft"}:
        if requirement.owner_id:
            return _run_requirement_transition(
                db,
                requirement,
                "assign",
                actor_id=actor_id,
                next_owner_id=requirement.owner_id,
            )
        return _run_requirement_transition(db, requirement, "claim", actor_id=actor_id)
    return requirement


def close_requirement(db: Session, requirement_id: int, payload: StatusOperationCreate, actor_id: int | None = None) -> Requirement:
    if not payload.reason:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Close reason is required")
    requirement = _get_active_requirement(db, requirement_id)
    ensure_work_item_action(db, requirement, actor_id, "需求")
    if payload.reason == "延期":
        result = defer_requirement_record(db, requirement, payload, actor_id=actor_id)
        db.commit()
        db.refresh(result)
        return result
    return close_requirement_record(db, requirement, payload, actor_id=actor_id)


def complete_requirement(db: Session, requirement_id: int, actor_id: int | None = None) -> Requirement:
    requirement = _get_active_requirement(db, requirement_id)
    ensure_work_item_action(db, requirement, actor_id, "需求")
    _ensure_project_open_for_requirement(db, requirement)
    if requirement.status in {"completed", "done"}:
        return requirement
    return _run_requirement_transition(db, requirement, "complete", actor_id=actor_id)


def close_requirement_record(
    db: Session,
    requirement: Requirement,
    payload: StatusOperationCreate,
    actor_id: int | None = None,
) -> Requirement:
    if requirement.status in {"completed", "done", "canceled", "closed"}:
        return requirement
    return _run_requirement_transition(db, requirement, "cancel", payload=payload, actor_id=actor_id)


def defer_requirement_record(
    db: Session,
    requirement: Requirement,
    payload: StatusOperationCreate,
    actor_id: int | None = None,
) -> Requirement:
    if payload.target_iteration_id and requirement.iteration_id == payload.target_iteration_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target iteration cannot be current iteration")
    if payload.target_iteration_id:
        _ensure_requirement_iteration_scope(db, requirement.project_id, payload.target_iteration_id)

    from_iteration_id = requirement.iteration_id
    from_status = requirement.status
    requirement.iteration_id = payload.target_iteration_id
    requirement.status = _initial_requirement_status(requirement.owner_id)
    linked_tasks = db.query(Task).filter(Task.requirement_id == requirement.id, Task.deleted == 0).all()
    for task in linked_tasks:
        task.iteration_id = payload.target_iteration_id
        if task.status not in {"completed", "canceled", "done", "closed"}:
            task.status = "pending_assignment"
    linked_test_cases = db.query(TestCase).filter(TestCase.requirement_id == requirement.id, TestCase.deleted == 0).all()
    for test_case in linked_test_cases:
        test_case.iteration_id = payload.target_iteration_id

    db.add(
        AuditLog(
            actor_id=actor_id,
            action="defer",
            object_type="requirement",
            object_id=requirement.id,
            before_data={"iteration_id": from_iteration_id, "status": from_status},
            after_data={"iteration_id": payload.target_iteration_id, "status": requirement.status},
        )
    )
    db.commit()
    db.refresh(requirement)
    return requirement


def list_requirement_status_operations(db: Session, requirement_id: int) -> list[dict]:
    _get_active_requirement(db, requirement_id)
    return list_status_operations(db, "requirement", requirement_id)


def list_requirement_audit_logs(db: Session, requirement_id: int) -> list[dict]:
    _get_active_requirement(db, requirement_id)
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.object_type == "requirement", AuditLog.object_id == requirement_id)
        .order_by(AuditLog.create_time.desc(), AuditLog.id.desc())
        .all()
    )
    return _audit_logs_with_actor_names(db, logs)


def delete_requirement(db: Session, requirement_id: int, actor_id: int | None = None) -> None:
    requirement = _get_active_requirement(db, requirement_id)
    _ensure_project_editable_for_requirement(db, requirement)
    linked_tasks = db.query(Task).filter(Task.requirement_id == requirement.id, Task.deleted == 0).all()
    for task in linked_tasks:
        task.requirement_id = None
        db.add(
            AuditLog(
                actor_id=actor_id,
                action="update",
                object_type="task",
                object_id=task.id,
                before_data={"requirement_id": requirement.id},
                after_data={"requirement_id": None},
            )
        )
    linked_test_cases = db.query(TestCase).filter(TestCase.requirement_id == requirement.id, TestCase.deleted == 0).all()
    for test_case in linked_test_cases:
        test_case.requirement_id = None
        db.add(
            AuditLog(
                actor_id=actor_id,
                action="update",
                object_type="test_case",
                object_id=test_case.id,
                before_data={"requirement_id": requirement.id},
                after_data={"requirement_id": None},
            )
        )
    requirement.deleted = 1
    requirement.delete_time = datetime.now()
    db.commit()


def generate_task_from_requirement(db: Session, requirement_id: int, payload: GenerateTaskRequest) -> Task:
    requirement = _get_active_requirement(db, requirement_id)
    owner_id = payload.owner_id if payload.owner_id is not None else requirement.owner_id
    task = Task(
        project_id=requirement.project_id,
        source_project_id=requirement.source_project_id,
        requirement_id=requirement.id,
        title=payload.title or requirement.title,
        task_type=payload.task_type,
        priority=payload.priority or requirement.priority,
        owner_id=owner_id,
        due_date=payload.due_date,
        status="in_processing" if owner_id else "pending_assignment",
        lifecycle_phase=requirement.lifecycle_phase,
        description=payload.description,
        source_requirement_review_status=requirement.review_status,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def _get_active_requirement(db: Session, requirement_id: int) -> Requirement:
    requirement = db.query(Requirement).filter(Requirement.id == requirement_id, Requirement.deleted == 0).first()
    if not requirement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
    return requirement


def _initial_requirement_status(owner_id: int | None) -> str:
    return "in_processing" if owner_id else "pending_assignment"


def _run_requirement_transition(
    db: Session,
    requirement: Requirement,
    action_key: str,
    *,
    payload: StatusOperationCreate | None = None,
    actor_id: int | None = None,
    next_owner_id: int | None = None,
) -> Requirement:
    actor = _actor_user(db, actor_id)
    request = WorkflowTransitionExecuteRequest(
        action_key=action_key,
        payload=_status_payload_dict(payload),
        next_owner_id=next_owner_id,
        delegate_reason=_delegate_reason(requirement.owner_id, actor, payload),
    )
    execute_transition(db, "requirement", requirement.id, request, actor)
    db.refresh(requirement)
    return requirement


def _actor_user(db: Session, actor_id: int | None) -> User | None:
    if not actor_id:
        return None
    return db.query(User).filter(User.id == actor_id).first()


def _status_payload_dict(payload: StatusOperationCreate | None) -> dict:
    return payload.model_dump(exclude_none=True) if payload else {}


def _delegate_reason(owner_id: int | None, actor: User | None, payload: StatusOperationCreate | None) -> str | None:
    if not actor:
        return None
    if owner_id == actor.id:
        return payload.delegate_reason if payload else None
    if payload and payload.delegate_reason:
        return payload.delegate_reason
    return "legacy requirement endpoint proxy"


def _ensure_project_open_for_requirement(db: Session, requirement: Requirement) -> None:
    project = db.query(Project).filter(Project.id == requirement.project_id, Project.deleted == 0).first()
    if project and project.status == "closed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project is closed")


def _ensure_project_editable_for_requirement(db: Session, requirement: Requirement) -> None:
    project = db.query(Project).filter(Project.id == requirement.project_id, Project.deleted == 0).first()
    if project and project.status == "closed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project is closed")


def _ensure_requirement_iteration_scope(db: Session, project_id: int | None, iteration_id: int | None) -> None:
    if not project_id or not iteration_id:
        return
    iteration = db.query(Iteration).filter(Iteration.id == iteration_id, Iteration.deleted == 0).first()
    if not iteration:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Iteration not found")
    if project_id not in _iteration_scoped_project_ids(db, iteration_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Requirement is outside iteration scope")


def _iteration_scoped_project_ids(db: Session, iteration_id: int) -> set[int]:
    root_ids = [row.project_id for row in db.query(IterationProject).filter(IterationProject.iteration_id == iteration_id).all()]
    result = set(root_ids)
    for project_id in root_ids:
        result.update(_collect_descendant_project_ids(db, project_id))
    return result


def _collect_descendant_project_ids(db: Session, project_id: int) -> set[int]:
    children = db.query(Project).filter(Project.parent_id == project_id, Project.deleted == 0).all()
    result = {child.id for child in children}
    for child in children:
        result.update(_collect_descendant_project_ids(db, child.id))
    return result


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


def _audit_logs_with_actor_names(db: Session, logs: list[AuditLog]) -> list[dict]:
    actor_ids = {log.actor_id for log in logs if log.actor_id}
    users = {}
    if actor_ids:
        users = {user.id: user.full_name for user in db.query(User).filter(User.id.in_(actor_ids)).all()}
    return [
        {
            "id": log.id,
            "actor_id": log.actor_id,
            "actor_name": users.get(log.actor_id) if log.actor_id else None,
            "action": log.action,
            "object_type": log.object_type,
            "object_id": log.object_id,
            "before_data": log.before_data,
            "after_data": log.after_data,
            "ip_address": log.ip_address,
            "user_agent": log.user_agent,
            "create_time": log.create_time,
        }
        for log in logs
    ]
