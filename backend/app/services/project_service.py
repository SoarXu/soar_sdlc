from sqlalchemy.orm import Session

from app.models.project import Project
from app.views.project_view import ProjectCreate


def list_projects(db: Session) -> list[Project]:
    projects = db.query(Project).order_by(Project.id.desc()).all()
    if projects:
        return projects

    seed = [
        Project(name="智享研发平台", status="active", description="系统初始化示例项目"),
        Project(name="临床协作套件", status="active", description="系统初始化示例项目"),
    ]
    db.add_all(seed)
    db.commit()
    return db.query(Project).order_by(Project.id.desc()).all()


def create_project(db: Session, payload: ProjectCreate) -> Project:
    project = Project(**payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project
