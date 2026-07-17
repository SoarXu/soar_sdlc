from datetime import date, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.bug import Bug
from app.models.project import Project
from app.models.relation import ObjectRelation
from app.models.requirement import Requirement
from app.models.task import Task
from app.models.test_case import TestCase
from app.models.test_run import TestRun
from app.models.user import User
from app.services.current_handler_service import ensure_work_item_action
from app.services.project_permission_service import (
    can_admin_action,
    ensure_authenticated,
    ensure_workflow_fields_not_updated,
    is_project_member,
)
from app.services.lifecycle_service import project_lifecycle_phase, requirement_lifecycle_phase
from app.services.status_operation_service import list_status_operations
from app.services.workflow_state_service import initial_workflow_values
from app.services.workflow_state_query_service import is_terminal_state
from app.views.task_view import LinkedTaskCreate, TaskCreate, TaskUpdate


LINKED_SOURCE_MODELS = {
    "requirement": Requirement,
    "bug": Bug,
    "test_case": TestCase,
    "test_run": TestRun,
}
LINKED_TASK_TYPES = {
    "requirement": "requirement_implementation",
    "bug": "bug_fix",
    "test_case": "test_support",
    "test_run": "test_support",
}


def list_tasks(db: Session) -> list[Task]:
    tasks = db.query(Task).filter(Task.deleted == 0).order_by(Task.id.desc()).all()
    for task in tasks:
        _attach_task_sources(db, task)
    return tasks


def get_task(db: Session, task_id: int) -> Task:
    task = _get_active_task(db, task_id)
    _attach_task_sources(db, task)
    return task


def create_task(db: Session, payload: TaskCreate, actor_id: int | None = None) -> Task:
    data = payload.model_dump()
    data["task_type"] = _resolved_task_type(data.get("task_type"), data.get("requirement_id"))
    data["creator_id"] = actor_id
    data["lifecycle_phase"] = (
        requirement_lifecycle_phase(db, data.get("requirement_id"))
        or project_lifecycle_phase(db, data.get("project_id"))
    )
    data.update(initial_workflow_values(db, "task", data.get("project_id")))
    task = Task(**data)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def create_linked_task(db: Session, payload: LinkedTaskCreate, actor: User | None) -> Task:
    ensure_authenticated(actor)
    source = _linked_source(db, payload.source_type, payload.source_id)
    project_id = getattr(source, "project_id", None)
    if not project_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Linked source has no project")
    project = db.query(Project).filter(Project.id == project_id, Project.deleted == 0).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linked source project not found")
    if is_terminal_state(project):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project is closed")

    inherited_owner_id = _linked_source_owner_id(payload.source_type, source)
    if actor.id != inherited_owner_id and not can_admin_action(db, project_id, actor.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only source handler or project administrator can create linked tasks")
    expected_task_type = LINKED_TASK_TYPES[payload.source_type]
    if payload.task_type and payload.task_type != expected_task_type:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Task branch conflicts with linked source type")

    final_owner_id = payload.owner_id if payload.owner_id is not None else inherited_owner_id
    owner_overridden = final_owner_id != inherited_owner_id
    if owner_overridden:
        if not can_admin_action(db, project_id, actor.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only project administrators can override linked task handler")
        if not payload.override_reason:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Handler override reason is required")
        if final_owner_id and not is_project_member(db, project_id, final_owner_id):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Selected handler is not a project member")

    workflow_values = initial_workflow_values(db, "task", project_id)
    task = Task(
        project_id=project_id,
        source_project_id=getattr(source, "source_project_id", None),
        iteration_id=getattr(source, "iteration_id", None),
        requirement_id=source.id if payload.source_type == "requirement" else None,
        title=payload.title,
        task_type=expected_task_type,
        priority=payload.priority,
        owner_id=final_owner_id,
        due_date=payload.due_date,
        **workflow_values,
        description=payload.description,
        lifecycle_phase=getattr(source, "lifecycle_phase", None) or project_lifecycle_phase(db, project_id),
        source_requirement_review_status=getattr(source, "review_status", None),
        creator_id=actor.id,
    )
    db.add(task)
    db.flush()
    db.add(
        ObjectRelation(
            source_type=payload.source_type,
            source_id=payload.source_id,
            target_type="task",
            target_id=task.id,
            relation_type="linked_task",
            creator_id=actor.id,
        )
    )
    db.add(
        AuditLog(
            actor_id=actor.id,
            action="create_linked_task",
            object_type="task",
            object_id=task.id,
            before_data={"source_type": payload.source_type, "source_id": payload.source_id},
            after_data={
                "creator_id": actor.id,
                "inherited_owner_id": inherited_owner_id,
                "final_owner_id": final_owner_id,
                "owner_overridden": owner_overridden,
                "override_reason": payload.override_reason,
                "task_type": expected_task_type,
            },
        )
    )
    db.commit()
    db.refresh(task)
    _attach_task_sources(db, task)
    return task


def linked_task_summaries(db: Session, source_type: str, source_id: int) -> list[dict]:
    task_ids = {
        relation.target_id
        for relation in db.query(ObjectRelation).filter(
            ObjectRelation.source_type == source_type,
            ObjectRelation.source_id == source_id,
            ObjectRelation.target_type == "task",
            ObjectRelation.relation_type == "linked_task",
        )
    }
    if source_type == "bug":
        bug = db.query(Bug).filter(Bug.id == source_id, Bug.deleted == 0).first()
        if bug and bug.task_id:
            task_ids.add(bug.task_id)
    if not task_ids:
        return []
    tasks = db.query(Task).filter(Task.id.in_(task_ids), Task.deleted == 0).order_by(Task.id.asc()).all()
    return [
        {
            "id": task.id,
            "title": task.title,
            "task_type": task.task_type,
            "status_name": task.status_name,
            "owner_id": task.owner_id,
        }
        for task in tasks
    ]


def update_task(db: Session, task_id: int, payload: TaskUpdate, actor_id: int | None = None) -> Task:
    task = _get_active_task(db, task_id)
    ensure_work_item_action(db, task, actor_id, "task")
    ensure_workflow_fields_not_updated(payload.model_fields_set)
    _ensure_project_editable_for_task(db, task)
    data = payload.model_dump(exclude_unset=True)
    data.pop("status", None)
    before_data, after_data = _task_change_data(task, data)
    for field, value in data.items():
        setattr(task, field, value)
    if before_data:
        db.add(
            AuditLog(
                actor_id=actor_id,
                action="update",
                object_type="task",
                object_id=task.id,
                before_data=before_data,
                after_data=after_data,
            )
        )
    db.commit()
    db.refresh(task)
    return task


def list_task_status_operations(db: Session, task_id: int) -> list[dict]:
    _get_active_task(db, task_id)
    return list_status_operations(db, "task", task_id)


def list_task_audit_logs(db: Session, task_id: int) -> list[dict]:
    _get_active_task(db, task_id)
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.object_type == "task", AuditLog.object_id == task_id)
        .order_by(AuditLog.create_time.desc(), AuditLog.id.desc())
        .all()
    )
    return _audit_logs_with_actor_names(db, logs)


def delete_task(db: Session, task_id: int) -> None:
    task = _get_active_task(db, task_id)
    _ensure_project_editable_for_task(db, task)
    task.deleted = 1
    task.delete_time = datetime.now()
    db.commit()


def _get_active_task(db: Session, task_id: int) -> Task:
    task = db.query(Task).filter(Task.id == task_id, Task.deleted == 0).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


def _linked_source(db: Session, source_type: str, source_id: int):
    model = LINKED_SOURCE_MODELS.get(source_type)
    if not model:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported linked source type")
    filters = [model.id == source_id]
    if hasattr(model, "deleted"):
        filters.append(model.deleted == 0)
    source = db.query(model).filter(*filters).first()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Linked source not found")
    return source


def _linked_source_owner_id(source_type: str, source) -> int | None:
    if source_type in {"requirement", "bug"}:
        return source.owner_id
    if source_type == "test_case":
        return source.default_tester_id
    if source_type == "test_run":
        return source.test_owner_id
    return None


def _attach_task_sources(db: Session, task: Task) -> None:
    relations = (
        db.query(ObjectRelation)
        .filter(
            ObjectRelation.target_type == "task",
            ObjectRelation.target_id == task.id,
            ObjectRelation.relation_type == "linked_task",
        )
        .order_by(ObjectRelation.id.asc())
        .all()
    )
    task.source_relations = [
        {
            "source_type": relation.source_type,
            "source_id": relation.source_id,
            "relation_type": relation.relation_type,
        }
        for relation in relations
    ]


def _initial_task_status(owner_id: int | None) -> str:
    return "in_processing" if owner_id else "pending_assignment"


def _resolved_task_type(task_type: str | None, requirement_id: int | None) -> str:
    if requirement_id:
        if task_type and task_type != "requirement_implementation":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Requirement-linked tasks must use requirement_implementation",
            )
        return "requirement_implementation"
    return task_type or "standalone_operation"


def _task_change_data(task: Task, data: dict) -> tuple[dict, dict]:
    before_data = {}
    after_data = {}
    for field, new_value in data.items():
        old_value = getattr(task, field)
        old_normalized = _audit_value(old_value)
        new_normalized = _audit_value(new_value)
        if old_normalized != new_normalized:
            before_data[field] = old_normalized
            after_data[field] = new_normalized
    return before_data, after_data


def _audit_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
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


def _ensure_project_editable_for_task(db: Session, task: Task) -> None:
    project = db.query(Project).filter(Project.id == task.project_id, Project.deleted == 0).first()
    if project and is_terminal_state(project):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project is closed")
