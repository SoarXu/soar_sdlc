from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.program import Program
from app.models.project import Project
from app.views.project_view import ProjectCreate, ProjectUpdate


def list_projects(db: Session) -> list[Project]:
    return db.query(Project).filter(Project.delete_time.is_(None)).order_by(Project.id.desc()).all()


def get_project(db: Session, project_id: int) -> Project:
    return _get_active_project(db, project_id)


def create_project(db: Session, payload: ProjectCreate) -> Project:
    data = payload.model_dump()
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


def start_project(db: Session, project_id: int) -> Project:
    project = _get_active_project(db, project_id)
    _require_status(project.status, {"planning"}, "只有规划中的项目可以启动")
    project.status = "active"
    _activate_program_tree(db, project.program_id)
    db.commit()
    db.refresh(project)
    return project


def suspend_project(db: Session, project_id: int) -> Project:
    project = _get_active_project(db, project_id)
    _require_status(project.status, {"active"}, "只有进行中的项目可以挂起")
    project.status = "paused"
    db.commit()
    db.refresh(project)
    return project


def close_project(db: Session, project_id: int) -> Project:
    project = _get_active_project(db, project_id)
    _require_status(project.status, {"active"}, "只有进行中的项目可以关闭")
    project.status = "closed"
    db.commit()
    db.refresh(project)
    return project


def activate_project(db: Session, project_id: int) -> Project:
    project = _get_active_project(db, project_id)
    _require_status(project.status, {"closed"}, "只有已关闭的项目可以激活")
    project.status = "active"
    _activate_program_tree(db, project.program_id)
    db.commit()
    db.refresh(project)
    return project


def _get_active_project(db: Session, project_id: int) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.delete_time.is_(None)).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


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
