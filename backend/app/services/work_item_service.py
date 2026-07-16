from datetime import datetime

from sqlalchemy.orm import Session

from app.models.bug import Bug
from app.models.iteration import Iteration
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.task import Task
from app.models.user import User
from app.services.project_permission_service import can_view_project_work_items, ensure_authenticated
from app.services.workflow_state_query_service import current_state_name, non_terminal_state_clause
from app.views.work_item_view import WorkItemListRead, WorkItemRead


MODEL_BY_TYPE = {
    "requirement": Requirement,
    "task": Task,
    "bug": Bug,
}
DEFAULT_OVERDUE_HOURS = {
    "1": 4,
    "2": 4,
    "3": 24,
    "4": 48,
    "5": 48,
    "high": 4,
    "medium": 24,
    "low": 48,
}


def list_unassigned_work_items(db: Session, actor: User | None) -> WorkItemListRead:
    ensure_authenticated(actor)
    projects = _project_map(db)
    iterations = _iteration_map(db)
    items = []
    for object_type, model in MODEL_BY_TYPE.items():
        rows = (
            db.query(model)
            .filter(
                model.deleted == 0,
                model.owner_id.is_(None),
                non_terminal_state_clause(model),
            )
            .all()
        )
        items.extend(
            _read_item(object_type, row, projects, iterations)
            for row in rows
            if can_view_project_work_items(db, row.project_id, actor)
        )
    items.sort(key=lambda item: (item.overdue is False, item.create_time or datetime.min, item.id))
    return WorkItemListRead(
        items=items,
        total=len(items),
        overdue_count=sum(1 for item in items if item.overdue),
    )


def _project_map(db: Session) -> dict[int, Project]:
    return {project.id: project for project in db.query(Project).filter(Project.deleted == 0).all()}


def _iteration_map(db: Session) -> dict[int, Iteration]:
    return {iteration.id: iteration for iteration in db.query(Iteration).filter(Iteration.deleted == 0).all()}


def _read_item(
    object_type: str,
    item,
    projects: dict[int, Project],
    iterations: dict[int, Iteration],
) -> WorkItemRead:
    waiting_hours = _waiting_hours(item.create_time)
    threshold = _overdue_threshold_hours(getattr(item, "priority", None) or getattr(item, "severity", None))
    return WorkItemRead(
        id=item.id,
        object_type=object_type,
        title=item.title,
        project_id=item.project_id,
        project_name=projects.get(item.project_id).name if item.project_id in projects else None,
        iteration_id=getattr(item, "iteration_id", None),
        iteration_name=iterations.get(item.iteration_id).name if getattr(item, "iteration_id", None) in iterations else None,
        status=current_state_name(item) or "",
        status_name=current_state_name(item),
        state_category=item.state_category,
        priority=getattr(item, "priority", None),
        severity=getattr(item, "severity", None),
        owner_id=item.owner_id,
        create_time=item.create_time,
        waiting_hours=waiting_hours,
        overdue=waiting_hours >= threshold,
    )


def _waiting_hours(create_time: datetime | None) -> float:
    if not create_time:
        return 0
    now = datetime.now(tz=create_time.tzinfo) if create_time.tzinfo else datetime.now()
    return max(0, round((now - create_time).total_seconds() / 3600, 2))


def _overdue_threshold_hours(priority: str | None) -> int:
    return DEFAULT_OVERDUE_HOURS.get(str(priority or "3").lower(), 24)
