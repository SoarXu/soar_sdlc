from datetime import date, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.task import Task
from app.models.test_case import TestCase
from app.models.user import User
from app.services.current_handler_service import ensure_work_item_action
from app.services.business_component_service import (
    attach_work_item_components,
    replace_work_item_components,
    resolve_primary_component,
)
from app.services.iteration_service import ensure_iteration_assignment_mutable
from app.services.project_permission_service import (
    ensure_work_item_create_permission,
    ensure_workflow_fields_not_updated,
    visible_project_ids,
)
from app.services.lifecycle_service import project_lifecycle_phase
from app.services.status_operation_service import list_status_operations
from app.services.task_service import linked_task_summaries
from app.services.work_item_iteration_history_service import (
    move_requirement_dependents_to_iteration,
    move_work_item_to_iteration,
)
from app.services.workflow_state_service import initial_work_item_workflow_values
from app.services.workflow_state_query_service import is_terminal_state
from app.services.iteration_assignment_service import validate_requirement_iteration
from app.views.requirement_view import RequirementCreate, RequirementUpdate


def list_requirements(db: Session, actor) -> list[Requirement]:
    requirements = db.query(Requirement).filter(
        Requirement.deleted == 0, Requirement.project_id.in_(visible_project_ids(db, actor))
    ).order_by(Requirement.id.desc()).all()
    for requirement in requirements:
        requirement.linked_tasks = linked_task_summaries(db, "requirement", requirement.id)
        attach_work_item_components(db, "requirement", requirement)
    return requirements


def get_requirement(db: Session, requirement_id: int) -> Requirement:
    requirement = _get_active_requirement(db, requirement_id)
    requirement.linked_tasks = linked_task_summaries(db, "requirement", requirement.id)
    attach_work_item_components(db, "requirement", requirement)
    return requirement


def create_requirement(db: Session, payload: RequirementCreate, actor_id: int | None = None) -> Requirement:
    data = payload.model_dump()
    primary_component_id = data.pop("primary_component_id", None)
    related_component_ids = data.pop("related_component_ids", [])
    data["creator_id"] = actor_id
    data["iteration_id"] = validate_requirement_iteration(
        db, data["project_id"], data.get("iteration_id")
    )
    ensure_iteration_assignment_mutable(db, None, data.get("iteration_id"))
    primary_component = resolve_primary_component(db, data["project_id"], primary_component_id)
    if primary_component:
        data["source_project_id"] = primary_component.source_project_id
    data.update(initial_work_item_workflow_values(
        db,
        "requirement",
        data.get("project_id"),
        data.get("owner_id"),
        data.get("iteration_id"),
        primary_component_id,
    ))
    data["lifecycle_phase"] = project_lifecycle_phase(db, data.get("project_id"))
    requirement = Requirement(**data)
    db.add(requirement)
    db.flush()
    replace_work_item_components(
        db,
        "requirement",
        requirement.id,
        requirement.project_id,
        primary_component_id,
        related_component_ids,
    )
    move_work_item_to_iteration(db, requirement, requirement.iteration_id, actor_id=actor_id, reason="created")
    db.commit()
    db.refresh(requirement)
    attach_work_item_components(db, "requirement", requirement)
    return requirement


def update_requirement(db: Session, requirement_id: int, payload: RequirementUpdate, actor_id: int | None = None) -> Requirement:
    requirement = _get_active_requirement(db, requirement_id)
    ensure_work_item_action(db, requirement, actor_id, "requirement")
    ensure_iteration_assignment_mutable(db, requirement.iteration_id, requirement.iteration_id)
    ensure_workflow_fields_not_updated(payload.model_fields_set)
    _ensure_project_editable_for_requirement(db, requirement)
    data = payload.model_dump(exclude_unset=True)
    data.pop("status", None)
    target_project_id = data.get("project_id", requirement.project_id)
    iteration_was_supplied = "iteration_id" in data
    requested_iteration_id = data.get("iteration_id") if iteration_was_supplied else requirement.iteration_id
    if target_project_id != requirement.project_id:
        actor = db.query(User).filter(User.id == actor_id, User.is_active.is_(True)).first()
        ensure_work_item_create_permission(db, target_project_id, actor)
        if not iteration_was_supplied:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="变更项目时必须同时选择迭代",
            )
    target_iteration_id = validate_requirement_iteration(db, target_project_id, requested_iteration_id)
    ensure_iteration_assignment_mutable(db, requirement.iteration_id, target_iteration_id)
    if target_iteration_id != requirement.iteration_id:
        data["iteration_id"] = target_iteration_id
    before_data, after_data = _requirement_change_data(requirement, data)
    scope_changed = (
        target_iteration_id != requirement.iteration_id
        or target_project_id != requirement.project_id
    )
    if scope_changed:
        source_iteration_id = requirement.iteration_id
        if target_iteration_id != requirement.iteration_id:
            move_work_item_to_iteration(
                db,
                requirement,
                target_iteration_id,
                actor_id=actor_id,
                reason="updated",
            )
        move_requirement_dependents_to_iteration(
            db,
            requirement.id,
            source_iteration_id,
            target_iteration_id,
            actor_id=actor_id,
            reason="requirement_updated",
            target_project_id=target_project_id,
        )
    data.pop("iteration_id", None)
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
    ensure_iteration_assignment_mutable(db, requirement.iteration_id, requirement.iteration_id)
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


def _get_active_requirement(db: Session, requirement_id: int) -> Requirement:
    requirement = db.query(Requirement).filter(Requirement.id == requirement_id, Requirement.deleted == 0).first()
    if not requirement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found")
    return requirement


def _ensure_project_editable_for_requirement(db: Session, requirement: Requirement) -> None:
    project = db.query(Project).filter(Project.id == requirement.project_id, Project.deleted == 0).first()
    if project and is_terminal_state(project):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project is closed")


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
