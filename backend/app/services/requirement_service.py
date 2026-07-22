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
from app.services.iteration_service import ensure_iteration_assignment_mutable
from app.services.project_permission_service import ensure_workflow_fields_not_updated
from app.services.lifecycle_service import project_lifecycle_phase
from app.services.status_operation_service import list_status_operations
from app.services.task_service import linked_task_summaries
from app.services.work_item_iteration_history_service import move_work_item_to_iteration
from app.services.workflow_state_service import initial_workflow_values
from app.services.workflow_state_query_service import is_terminal_state
from app.views.requirement_view import RequirementCreate, RequirementUpdate


def list_requirements(db: Session) -> list[Requirement]:
    requirements = db.query(Requirement).filter(Requirement.deleted == 0).order_by(Requirement.id.desc()).all()
    for requirement in requirements:
        requirement.linked_tasks = linked_task_summaries(db, "requirement", requirement.id)
    return requirements


def get_requirement(db: Session, requirement_id: int) -> Requirement:
    requirement = _get_active_requirement(db, requirement_id)
    requirement.linked_tasks = linked_task_summaries(db, "requirement", requirement.id)
    return requirement


def create_requirement(db: Session, payload: RequirementCreate, actor_id: int | None = None) -> Requirement:
    data = payload.model_dump()
    data["creator_id"] = actor_id
    ensure_iteration_assignment_mutable(db, None, data.get("iteration_id"))
    _ensure_requirement_iteration_scope(db, data.get("project_id"), data.get("iteration_id"))
    data.update(initial_workflow_values(db, "requirement", data.get("project_id")))
    data["lifecycle_phase"] = project_lifecycle_phase(db, data.get("project_id"))
    requirement = Requirement(**data)
    db.add(requirement)
    db.flush()
    if requirement.iteration_id:
        move_work_item_to_iteration(db, requirement, requirement.iteration_id, actor_id=actor_id, reason="created")
    db.commit()
    db.refresh(requirement)
    return requirement


def update_requirement(db: Session, requirement_id: int, payload: RequirementUpdate, actor_id: int | None = None) -> Requirement:
    requirement = _get_active_requirement(db, requirement_id)
    ensure_iteration_assignment_mutable(db, requirement.iteration_id, requirement.iteration_id)
    ensure_work_item_action(db, requirement, actor_id, "requirement")
    ensure_workflow_fields_not_updated(payload.model_fields_set)
    _ensure_project_editable_for_requirement(db, requirement)
    data = payload.model_dump(exclude_unset=True)
    data.pop("status", None)
    target_project_id = data.get("project_id", requirement.project_id)
    target_iteration_id = data.get("iteration_id", requirement.iteration_id)
    ensure_iteration_assignment_mutable(db, requirement.iteration_id, target_iteration_id)
    _ensure_requirement_iteration_scope(db, target_project_id, target_iteration_id)
    before_data, after_data = _requirement_change_data(requirement, data)
    if "iteration_id" in data:
        move_work_item_to_iteration(
            db,
            requirement,
            data.pop("iteration_id"),
            actor_id=actor_id,
            reason="updated",
        )
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
