from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.bug import Bug
from app.models.program import Program
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.task import Task
from app.views.dashboard_view import DashboardSummary


def get_dashboard_summary(db: Session) -> DashboardSummary:
    return DashboardSummary(
        programs=_count_active(db, Program),
        projects=_count_active(db, Project),
        requirements=_count_active(db, Requirement),
        tasks=_count_active(db, Task),
        open_bugs=db.query(func.count(Bug.id)).filter(Bug.deleted == 0, Bug.status != "closed").scalar()
        or 0,
    )


def _count_active(db: Session, model) -> int:
    return db.query(func.count(model.id)).filter(model.deleted == 0).scalar() or 0
