from datetime import date, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.bug import Bug
from app.models.iteration import Iteration, IterationProject
from app.models.program import Program
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.task import Task
from app.models.test_case import TestCase
from app.models.test_run import TestRun
from app.services.status_operation_service import create_status_operation, list_status_operations
from app.services.requirement_service import close_requirement_record
from app.services.workflow_engine import execute_workflows
from app.views.project_view import ProjectCreate, ProjectUpdate
from app.views.status_operation_view import StatusOperationCreate


MAINTENANCE_STATUS = "maintenance"
DEVELOPMENT_PHASE = "development"
MAINTENANCE_PHASE = "maintenance"


def list_projects(db: Session) -> list[Project]:
    return db.query(Project).filter(Project.deleted == 0).order_by(Project.id.asc()).all()


def get_project(db: Session, project_id: int) -> Project:
    return _get_active_project(db, project_id)


def create_project(db: Session, payload: ProjectCreate) -> Project:
    data = payload.model_dump()
    data["lifecycle_phase"] = DEVELOPMENT_PHASE
    data["maintenance_start_time"] = None
    parent = None
    if data.get("parent_id"):
        parent = _get_active_project(db, data["parent_id"])
        if not data.get("program_id"):
            data["program_id"] = parent.program_id
    if data.get("is_long_term"):
        data["end_date"] = None
    data["status"] = "planning"
    project = Project(**data)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def update_project(db: Session, project_id: int, payload: ProjectUpdate) -> Project:
    project = _get_active_project(db, project_id)
    data = payload.model_dump(exclude_unset=True)
    maintenance_remark = data.pop("maintenance_remark", None)
    data.pop("lifecycle_phase", None)
    if data.get("parent_id") == project_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="项目不能选择自身作为上级项目")
    old_parent_id = project.parent_id
    should_move_to_maintenance = (
        "parent_id" in data
        and data.get("parent_id") is not None
        and data.get("parent_id") != old_parent_id
        and project.status == "closed"
    )
    if data.get("parent_id"):
        parent = _get_active_project(db, data["parent_id"])
        if _is_project_descendant_of(db, parent, project_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="项目不能选择下级项目作为上级项目")
    if data.get("is_long_term"):
        data["end_date"] = None
    data.pop("status", None)
    maintenance_start_time = data.pop("maintenance_start_time", None)
    before_data, after_data = _project_change_data(project, data)
    for field, value in data.items():
        setattr(project, field, value)
    if before_data:
        db.add(
            AuditLog(
                action="update",
                object_type="project",
                object_id=project.id,
                before_data=before_data,
                after_data=after_data,
            )
        )
    if should_move_to_maintenance:
        effective_time = maintenance_start_time or datetime.now()
        from_status = project.status
        project.status = MAINTENANCE_STATUS
        project.lifecycle_phase = MAINTENANCE_PHASE
        project.maintenance_start_time = effective_time
        create_status_operation(
            db,
            object_type="project",
            object_id=project.id,
            action="move_to_maintenance",
            from_status=from_status,
            to_status=project.status,
            payload=StatusOperationCreate(effective_time=effective_time, remark=maintenance_remark),
        )
    db.commit()
    db.refresh(project)
    return project


def list_project_audit_logs(db: Session, project_id: int) -> list[AuditLog]:
    _get_active_project(db, project_id)
    return (
        db.query(AuditLog)
        .filter(AuditLog.object_type == "project", AuditLog.object_id == project_id)
        .order_by(AuditLog.create_time.desc(), AuditLog.id.desc())
        .all()
    )


def delete_project(db: Session, project_id: int) -> None:
    project = _get_active_project(db, project_id)
    now = datetime.now()

    project_ids = {project_id}
    project_ids.update(_collect_descendant_project_ids(db, project_id))
    _cascade_delete_project_work_items(db, project_ids, now)

    descendant_ids = project_ids - {project_id}
    projects_to_delete = (
        db.query(Project)
        .filter(Project.id.in_(descendant_ids), Project.deleted == 0)
        .all()
    )
    for p in projects_to_delete:
        p.deleted = 1
        p.delete_time = now

    project.deleted = 1
    project.delete_time = now
    db.commit()


def start_project(db: Session, project_id: int, payload: StatusOperationCreate | None = None) -> Project:
    project = _get_active_project(db, project_id)
    _require_status(project.status, {"planning", "paused"}, "只有规划中或已挂起的项目可以启动")
    from_status = project.status
    project.status = "active"
    if from_status == "planning":
        _require_effective_time(payload, "请选择实际开始日期")
        project.actual_start_date = _effective_date(payload)
    _activate_program_tree(db, project.program_id)
    create_status_operation(
        db,
        object_type="project",
        object_id=project.id,
        action="start",
        from_status=from_status,
        to_status=project.status,
        payload=payload,
    )
    db.commit()
    db.refresh(project)
    return project


def suspend_project(db: Session, project_id: int, payload: StatusOperationCreate | None = None) -> Project:
    project = _get_active_project(db, project_id)
    _require_status(project.status, {"active"}, "只有进行中的项目可以挂起")
    from_status = project.status
    project.status = "paused"
    create_status_operation(
        db,
        object_type="project",
        object_id=project.id,
        action="suspend",
        from_status=from_status,
        to_status=project.status,
        payload=payload,
    )
    db.commit()
    db.refresh(project)
    return project


def close_project(db: Session, project_id: int, payload: StatusOperationCreate | None = None) -> Project:
    project = _get_active_project(db, project_id)
    _require_status(project.status, {"active", "paused", MAINTENANCE_STATUS}, "只有进行中、已挂起或运维中的项目可以关闭")
    from_status = project.status
    _require_effective_time(payload, "请选择实际完成日期")
    workflow_result = execute_workflows(
        db,
        target_object="project",
        trigger_action="status_changed",
        context={
            "target_object": "project",
            "object_id": project.id,
            "from_status": from_status,
            "to_status": "closed",
            "effective_time": payload.effective_time if payload else None,
            "reason": payload.reason if payload else None,
            "remark": payload.remark if payload else None,
        },
    )
    project.status = "closed"
    project.actual_end_date = _effective_date(payload)
    if not workflow_result.has_action("batch_change_child_status"):
        cascade_payload = StatusOperationCreate(reason="不做", remark=payload.remark if payload else None)
        requirements = (
            db.query(Requirement)
            .filter(Requirement.project_id == project.id, Requirement.deleted == 0, Requirement.status != "closed")
            .all()
        )
        for requirement in requirements:
            close_requirement_record(db, requirement, cascade_payload)
        orphan_tasks = (
            db.query(Task)
            .filter(Task.project_id == project.id, Task.deleted == 0, Task.requirement_id.is_(None), Task.status != "closed")
            .all()
        )
        for task in orphan_tasks:
            from app.services.task_service import close_task_record

            close_task_record(db, task, cascade_payload)
    create_status_operation(
        db,
        object_type="project",
        object_id=project.id,
        action="close",
        from_status=from_status,
        to_status=project.status,
        payload=payload,
    )
    db.commit()
    db.refresh(project)
    return project


def activate_project(db: Session, project_id: int, payload: StatusOperationCreate | None = None) -> Project:
    project = _get_active_project(db, project_id)
    _require_status(project.status, {"closed"}, "只有已关闭的项目可以激活")
    from_status = project.status
    project.status = "active"
    project.actual_end_date = None
    project.lifecycle_phase = DEVELOPMENT_PHASE
    project.maintenance_start_time = None
    _activate_program_tree(db, project.program_id)
    create_status_operation(
        db,
        object_type="project",
        object_id=project.id,
        action="activate",
        from_status=from_status,
        to_status=project.status,
        payload=payload,
    )
    db.commit()
    db.refresh(project)
    return project


def list_project_status_operations(db: Session, project_id: int) -> list[dict]:
    _get_active_project(db, project_id)
    return list_status_operations(db, "project", project_id)


def _get_active_project(db: Session, project_id: int) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.deleted == 0).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _is_project_descendant_of(db: Session, project: Project, ancestor_id: int) -> bool:
    visited: set[int] = set()
    current = project
    while current.parent_id:
        if current.parent_id == ancestor_id:
            return True
        if current.parent_id in visited:
            return False
        visited.add(current.parent_id)
        current = db.query(Project).filter(Project.id == current.parent_id, Project.deleted == 0).first()
        if current is None:
            return False
    return False


def _require_status(current_status: str, allowed_statuses: set[str], message: str) -> None:
    if current_status not in allowed_statuses:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


def _require_effective_time(payload: StatusOperationCreate | None, message: str) -> None:
    if not payload or not payload.effective_time:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


def _activate_program_tree(db: Session, program_id: int | None) -> None:
    while program_id:
        program = db.query(Program).filter(Program.id == program_id, Program.deleted == 0).first()
        if not program:
            return
        if program.status != "active":
            program.status = "active"
        program_id = program.parent_id


def _effective_date(payload: StatusOperationCreate | None) -> date:
    if payload and payload.effective_time:
        return payload.effective_time.date()
    return date.today()


def _project_change_data(project: Project, data: dict) -> tuple[dict, dict]:
    before_data = {}
    after_data = {}
    for field, new_value in data.items():
        old_value = getattr(project, field)
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


def _collect_descendant_project_ids(db: Session, project_id: int) -> set[int]:
    result: set[int] = set()
    children = db.query(Project).filter(Project.parent_id == project_id, Project.deleted == 0).all()
    for child in children:
        result.add(child.id)
        result.update(_collect_descendant_project_ids(db, child.id))
    return result


def _cascade_delete_project_work_items(db: Session, project_ids: set[int], deleted_at: datetime) -> None:
    _soft_delete_by_project_ids(db, Requirement, project_ids, deleted_at)
    _soft_delete_by_project_ids(db, Task, project_ids, deleted_at)
    _soft_delete_by_project_ids(db, TestCase, project_ids, deleted_at)
    _soft_delete_by_project_ids(db, Bug, project_ids, deleted_at)
    _soft_delete_by_project_ids(db, TestRun, project_ids, deleted_at)
    _delete_iteration_project_scope(db, project_ids, deleted_at)


def _soft_delete_by_project_ids(db: Session, model, project_ids: set[int], deleted_at: datetime) -> None:
    items = db.query(model).filter(model.project_id.in_(project_ids), model.deleted == 0).all()
    for item in items:
        item.deleted = 1
        item.delete_time = deleted_at


def _delete_iteration_project_scope(db: Session, project_ids: set[int], deleted_at: datetime) -> None:
    affected_iteration_ids = {
        row.iteration_id
        for row in db.query(IterationProject).filter(IterationProject.project_id.in_(project_ids)).all()
    }
    if not affected_iteration_ids:
        return
    db.query(IterationProject).filter(IterationProject.project_id.in_(project_ids)).delete(synchronize_session=False)
    for iteration_id in affected_iteration_ids:
        remaining_scope_exists = (
            db.query(IterationProject)
            .filter(IterationProject.iteration_id == iteration_id)
            .first()
            is not None
        )
        if not remaining_scope_exists:
            iteration = db.query(Iteration).filter(Iteration.id == iteration_id, Iteration.deleted == 0).first()
            if iteration:
                iteration.deleted = 1
                iteration.delete_time = deleted_at
