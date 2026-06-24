from datetime import date, datetime

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.bug import Bug
from app.models.iteration import Iteration, IterationProject
from app.models.program import Program
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.requirement import Requirement
from app.models.task import Task
from app.models.test_case import TestCase
from app.models.test_case_execution import TestCaseExecutionLog
from app.models.test_run import TestRun, TestRunCase
from app.services.status_operation_service import create_status_operation, list_status_operations
from app.services.requirement_service import close_requirement_record
from app.services.workflow_engine import execute_workflows
from app.views.project_view import ProjectCreate, ProjectMemberCreate, ProjectUpdate
from app.views.status_operation_view import StatusOperationCreate


def list_projects(db: Session) -> list[Project]:
    return db.query(Project).filter(Project.deleted == 0).order_by(Project.id.asc()).all()


def list_project_iterations_page(
    db: Session,
    project_id: int,
    page: int = 1,
    page_size: int = 10,
    keyword: str | None = None,
    status: str | None = None,
    owner_id: int | None = None,
) -> dict:
    _get_active_project(db, project_id)
    query = (
        db.query(Iteration)
        .join(IterationProject, IterationProject.iteration_id == Iteration.id)
        .filter(Iteration.deleted == 0, IterationProject.project_id == project_id)
    )
    if keyword:
        query = query.filter(Iteration.name.like(f"%{keyword}%"))
    if status:
        query = query.filter(Iteration.status == status)
    if owner_id:
        query = query.filter(Iteration.owner_id == owner_id)
    page_data = _paginate(query.order_by(Iteration.id.desc()), page, page_size)
    page_data["items"] = [_iteration_to_dict(db, item) for item in page_data["items"]]
    return page_data


def list_project_requirements_page(
    db: Session,
    project_id: int,
    page: int = 1,
    page_size: int = 10,
    keyword: str | None = None,
    status: str | None = None,
    owner_id: int | None = None,
    iteration_id: int | None = None,
) -> dict:
    _get_active_project(db, project_id)
    query = db.query(Requirement).filter(Requirement.deleted == 0, Requirement.project_id == project_id)
    if keyword:
        query = query.filter(Requirement.title.like(f"%{keyword}%"))
    if status:
        query = query.filter(Requirement.status == status)
    if owner_id:
        query = query.filter(Requirement.owner_id == owner_id)
    if iteration_id:
        query = query.filter(Requirement.iteration_id == iteration_id)
    return _paginate(query.order_by(Requirement.id.desc()), page, page_size)


def list_project_tasks_page(
    db: Session,
    project_id: int,
    page: int = 1,
    page_size: int = 10,
    keyword: str | None = None,
    status: str | None = None,
    owner_id: int | None = None,
    requirement_id: int | None = None,
) -> dict:
    _get_active_project(db, project_id)
    query = db.query(Task).filter(Task.deleted == 0, Task.project_id == project_id)
    if keyword:
        query = query.filter(Task.title.like(f"%{keyword}%"))
    if status:
        query = query.filter(Task.status == status)
    if owner_id:
        query = query.filter(Task.owner_id == owner_id)
    if requirement_id:
        query = query.filter(Task.requirement_id == requirement_id)
    return _paginate(query.order_by(Task.id.desc()), page, page_size)


def list_project_test_cases_page(
    db: Session,
    project_id: int,
    page: int = 1,
    page_size: int = 10,
    keyword: str | None = None,
    result: str | None = None,
    requirement_id: int | None = None,
) -> dict:
    _get_active_project(db, project_id)
    query = db.query(TestCase).filter(TestCase.deleted == 0, TestCase.project_id == project_id)
    if keyword:
        query = query.filter(TestCase.title.like(f"%{keyword}%"))
    if result:
        query = query.filter(TestCase.last_execute_result == result)
    if requirement_id:
        query = query.filter(TestCase.requirement_id == requirement_id)
    return _paginate(query.order_by(TestCase.id.desc()), page, page_size)


def list_project_test_runs_page(
    db: Session,
    project_id: int,
    page: int = 1,
    page_size: int = 10,
    keyword: str | None = None,
    status: str | None = None,
    owner_id: int | None = None,
    iteration_id: int | None = None,
) -> dict:
    _get_active_project(db, project_id)
    query = db.query(TestRun).filter(TestRun.deleted == 0, TestRun.project_id == project_id)
    if keyword:
        query = query.filter(TestRun.name.like(f"%{keyword}%"))
    if status:
        query = query.filter(TestRun.status == status)
    if owner_id:
        query = query.filter(TestRun.test_owner_id == owner_id)
    if iteration_id:
        query = query.filter(TestRun.iteration_id == iteration_id)
    return _paginate(query.order_by(TestRun.id.desc()), page, page_size)


def list_project_bugs_page(
    db: Session,
    project_id: int,
    page: int = 1,
    page_size: int = 10,
    keyword: str | None = None,
    status: str | None = None,
    owner_id: int | None = None,
    iteration_id: int | None = None,
) -> dict:
    _get_active_project(db, project_id)
    query = db.query(Bug).filter(Bug.deleted == 0, Bug.project_id == project_id)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(or_(Bug.title.like(like), Bug.bug_type.like(like)))
    if status:
        query = query.filter(Bug.status == status)
    if owner_id:
        query = query.filter(Bug.owner_id == owner_id)
    if iteration_id:
        query = query.filter(Bug.iteration_id == iteration_id)
    return _paginate(query.order_by(Bug.id.desc()), page, page_size)


def get_project(db: Session, project_id: int) -> Project:
    return _get_active_project(db, project_id)


def create_project(db: Session, payload: ProjectCreate) -> Project:
    data = payload.model_dump()
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
    data.pop("lifecycle_phase", None)
    data.pop("maintenance_start_time", None)
    data.pop("maintenance_remark", None)
    if data.get("parent_id") == project_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="项目不能选择自身作为上级项目")
    if data.get("parent_id"):
        parent = _get_active_project(db, data["parent_id"])
        if _is_project_descendant_of(db, parent, project_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="项目不能选择下级项目作为上级项目")
    if data.get("is_long_term"):
        data["end_date"] = None
    data.pop("status", None)
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


def list_project_members(db: Session, project_id: int) -> list[ProjectMember]:
    _get_active_project(db, project_id)
    return (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.sort_order.asc(), ProjectMember.id.asc())
        .all()
    )


def replace_project_members(db: Session, project_id: int, payload: list[ProjectMemberCreate]) -> list[ProjectMember]:
    _get_active_project(db, project_id)
    db.query(ProjectMember).filter(ProjectMember.project_id == project_id).delete(synchronize_session=False)
    for index, item in enumerate(payload):
        data = item.model_dump()
        data["project_id"] = project_id
        if not data.get("sort_order"):
            data["sort_order"] = index
        db.add(ProjectMember(**data))
    db.commit()
    return list_project_members(db, project_id)


def start_project(db: Session, project_id: int, payload: StatusOperationCreate | None = None, actor_id: int | None = None) -> Project:
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
        actor_id=actor_id,
    )
    db.commit()
    db.refresh(project)
    return project


def suspend_project(db: Session, project_id: int, payload: StatusOperationCreate | None = None, actor_id: int | None = None) -> Project:
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
        actor_id=actor_id,
    )
    db.commit()
    db.refresh(project)
    return project


def close_project(db: Session, project_id: int, payload: StatusOperationCreate | None = None, actor_id: int | None = None) -> Project:
    project = _get_active_project(db, project_id)
    _require_status(project.status, {"active", "paused"}, "只有进行中或已挂起的项目可以关闭")
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
            "operator_id": actor_id,
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
            close_requirement_record(db, requirement, cascade_payload, actor_id=actor_id)
        orphan_tasks = (
            db.query(Task)
            .filter(Task.project_id == project.id, Task.deleted == 0, Task.requirement_id.is_(None), Task.status != "closed")
            .all()
        )
        for task in orphan_tasks:
            from app.services.task_service import close_task_record

            close_task_record(db, task, cascade_payload, actor_id=actor_id)
    create_status_operation(
        db,
        object_type="project",
        object_id=project.id,
        action="close",
        from_status=from_status,
        to_status=project.status,
        payload=payload,
        actor_id=actor_id,
    )
    db.commit()
    db.refresh(project)
    return project


def activate_project(db: Session, project_id: int, payload: StatusOperationCreate | None = None, actor_id: int | None = None) -> Project:
    project = _get_active_project(db, project_id)
    _require_status(project.status, {"closed"}, "只有已关闭的项目可以激活")
    from_status = project.status
    project.status = "active"
    project.actual_end_date = None
    _activate_program_tree(db, project.program_id)
    create_status_operation(
        db,
        object_type="project",
        object_id=project.id,
        action="activate",
        from_status=from_status,
        to_status=project.status,
        payload=payload,
        actor_id=actor_id,
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


def _paginate(query, page: int, page_size: int) -> dict:
    normalized_page = max(page or 1, 1)
    normalized_page_size = min(max(page_size or 10, 1), 100)
    total = query.count()
    items = query.offset((normalized_page - 1) * normalized_page_size).limit(normalized_page_size).all()
    return {
        "items": items,
        "total": total,
        "page": normalized_page,
        "page_size": normalized_page_size,
    }


def _iteration_to_dict(db: Session, iteration: Iteration) -> dict:
    project_ids = [
        item.project_id
        for item in db.query(IterationProject).filter(IterationProject.iteration_id == iteration.id).all()
    ]
    return {
        "id": iteration.id,
        "project_id": project_ids[0] if project_ids else None,
        "project_ids": project_ids,
        "name": iteration.name,
        "owner_id": iteration.owner_id,
        "start_date": iteration.start_date,
        "end_date": iteration.end_date,
        "actual_start_date": iteration.actual_start_date,
        "actual_end_date": iteration.actual_end_date,
        "status": iteration.status,
        "lifecycle_phase": iteration.lifecycle_phase,
        "goal": iteration.goal,
        "creator_id": iteration.creator_id,
        "updater_id": iteration.updater_id,
        "create_time": iteration.create_time,
        "update_time": iteration.update_time,
        "delete_time": iteration.delete_time,
    }


def _collect_descendant_project_ids(db: Session, project_id: int) -> set[int]:
    result: set[int] = set()
    children = db.query(Project).filter(Project.parent_id == project_id, Project.deleted == 0).all()
    for child in children:
        result.add(child.id)
        result.update(_collect_descendant_project_ids(db, child.id))
    return result


def _cascade_delete_project_work_items(db: Session, project_ids: set[int], deleted_at: datetime) -> None:
    test_case_ids = {
        row.id for row in db.query(TestCase.id).filter(TestCase.project_id.in_(project_ids), TestCase.deleted == 0).all()
    }
    test_run_ids = {
        row.id for row in db.query(TestRun.id).filter(TestRun.project_id.in_(project_ids), TestRun.deleted == 0).all()
    }
    if test_case_ids:
        db.query(TestCaseExecutionLog).filter(TestCaseExecutionLog.test_case_id.in_(test_case_ids)).delete(
            synchronize_session=False
        )
        db.query(TestRunCase).filter(TestRunCase.test_case_id.in_(test_case_ids)).delete(synchronize_session=False)
    if test_run_ids:
        db.query(TestRunCase).filter(TestRunCase.test_run_id.in_(test_run_ids)).delete(synchronize_session=False)
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
