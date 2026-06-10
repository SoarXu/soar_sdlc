from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.program import Program
from app.models.project import Project
from app.services.status_operation_service import create_status_operation, list_status_operations
from app.views.project_view import ProjectCreate, ProjectUpdate
from app.views.status_operation_view import StatusOperationCreate


def list_projects(db: Session) -> list[Project]:
    return db.query(Project).filter(Project.delete_time.is_(None)).order_by(Project.id.asc()).all()


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
    if data.get("parent_id") == project_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="项目不能选择自身作为上级项目")
    if data.get("parent_id"):
        parent = _get_active_project(db, data["parent_id"])
        if _is_project_descendant_of(db, parent, project_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="项目不能选择下级项目作为上级项目")
    if data.get("is_long_term"):
        data["end_date"] = None
    data.pop("status", None)
    for field, value in data.items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, project_id: int) -> None:
    project = _get_active_project(db, project_id)
    project.delete_time = datetime.now()
    db.commit()


def start_project(db: Session, project_id: int, payload: StatusOperationCreate | None = None) -> Project:
    project = _get_active_project(db, project_id)
    _require_status(project.status, {"planning", "paused"}, "只有规划中或已挂起的项目可以启动")
    from_status = project.status
    project.status = "active"
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
    _require_status(project.status, {"active", "paused"}, "只有进行中或已挂起的项目可以关闭")
    from_status = project.status
    project.status = "closed"
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
    project = db.query(Project).filter(Project.id == project_id, Project.delete_time.is_(None)).first()
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
        current = db.query(Project).filter(Project.id == current.parent_id, Project.delete_time.is_(None)).first()
        if current is None:
            return False
    return False


def _require_status(current_status: str, allowed_statuses: set[str], message: str) -> None:
    if current_status not in allowed_statuses:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


def _activate_program_tree(db: Session, program_id: int | None) -> None:
    while program_id:
        program = db.query(Program).filter(Program.id == program_id, Program.delete_time.is_(None)).first()
        if not program:
            return
        if program.status != "active":
            program.status = "active"
        program_id = program.parent_id
