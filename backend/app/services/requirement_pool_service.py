from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.bug import Bug
from app.models.iteration import Iteration, IterationProject
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.task import Task
from app.services.lifecycle_service import project_lifecycle_phase
from app.services.workflow_state_query_service import non_terminal_state_clause
from app.services.workflow_state_service import initial_system_workflow_values


POOL_INTEGRITY_ERROR = "REQUIREMENT_POOL_INTEGRITY_ERROR"


def create_project_requirement_pool(
    db: Session,
    project: Project,
    workflow_values: dict | None = None,
) -> Iteration:
    workflow_values = workflow_values or initial_system_workflow_values(db, "iteration")
    pool = Iteration(
        name="需求池",
        is_requirement_pool=True,
        lifecycle_phase=project_lifecycle_phase(db, project.id),
        **workflow_values,
    )
    db.add(pool)
    db.flush()
    db.add(IterationProject(iteration_id=pool.id, project_id=project.id))
    project.requirement_pool_iteration_id = pool.id
    return pool


def requirement_pool_for_project(db: Session, project_id: int, *, for_update: bool = False) -> Iteration:
    project_query = db.query(Project).filter(Project.id == project_id, Project.deleted == 0)
    if for_update:
        project_query = project_query.with_for_update()
    project = project_query.first()
    if not project or project.requirement_pool_iteration_id is None:
        _raise_pool_integrity_error(project_id)

    pool_query = db.query(Iteration).filter(
        Iteration.id == project.requirement_pool_iteration_id,
        Iteration.deleted == 0,
    )
    if for_update:
        pool_query = pool_query.with_for_update()
    pool = pool_query.first()
    if not pool or not pool.is_requirement_pool:
        _raise_pool_integrity_error(project_id)

    membership_query = db.query(IterationProject).filter(IterationProject.iteration_id == pool.id)
    if for_update:
        membership_query = membership_query.with_for_update()
    memberships = membership_query.all()
    if len(memberships) != 1 or memberships[0].project_id != project.id:
        _raise_pool_integrity_error(project_id)
    return pool


def resolve_requirement_iteration_id(
    db: Session,
    project_id: int,
    requested_iteration_id: int | None,
) -> int:
    if requested_iteration_id is None:
        return requirement_pool_for_project(db, project_id).id

    iteration = db.query(Iteration).filter(
        Iteration.id == requested_iteration_id,
        Iteration.deleted == 0,
    ).first()
    if not iteration:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Iteration not found")
    if project_id not in _iteration_scoped_project_ids(db, requested_iteration_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Requirement is outside iteration scope")
    if iteration.is_requirement_pool and requirement_pool_for_project(db, project_id).id != requested_iteration_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Requirement pool is not canonical for project")
    return requested_iteration_id


def resolve_project_work_item_iteration_id(
    db: Session,
    project_id: int,
    requested_iteration_id: int | None,
    *,
    source_iteration_id: int | None = None,
) -> int:
    if requested_iteration_id is not None:
        return requested_iteration_id
    if source_iteration_id is not None:
        return source_iteration_id
    return requirement_pool_for_project(db, project_id).id


def is_project_requirement_pool(db: Session, project_id: int, iteration_id: int | None) -> bool:
    return iteration_id is not None and requirement_pool_for_project(db, project_id).id == iteration_id


def project_work_pool_counts(db: Session, project_id: int) -> dict[str, int]:
    pool_id = requirement_pool_for_project(db, project_id).id
    counts = {
        "requirement_count": _open_pool_item_count(db, Requirement, pool_id),
        "task_count": _open_pool_item_count(db, Task, pool_id),
        "bug_count": _open_pool_item_count(db, Bug, pool_id),
    }
    counts["total_count"] = sum(counts.values())
    return counts


def _open_pool_item_count(db: Session, model, pool_id: int) -> int:
    return int(
        db.query(func.count(model.id))
        .filter(
            model.deleted == 0,
            model.iteration_id == pool_id,
            non_terminal_state_clause(model),
        )
        .scalar()
        or 0
    )


def _iteration_scoped_project_ids(db: Session, iteration_id: int) -> set[int]:
    root_ids = [
        row.project_id
        for row in db.query(IterationProject).filter(IterationProject.iteration_id == iteration_id).all()
    ]
    project_ids = set(root_ids)
    for project_id in root_ids:
        project_ids.update(_descendant_project_ids(db, project_id))
    return project_ids


def _descendant_project_ids(db: Session, project_id: int) -> set[int]:
    children = db.query(Project).filter(Project.parent_id == project_id, Project.deleted == 0).all()
    project_ids = {child.id for child in children}
    for child in children:
        project_ids.update(_descendant_project_ids(db, child.id))
    return project_ids


def _raise_pool_integrity_error(project_id: int) -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": POOL_INTEGRITY_ERROR,
            "message": "Project requirement pool integrity check failed",
            "project_id": project_id,
        },
    )
