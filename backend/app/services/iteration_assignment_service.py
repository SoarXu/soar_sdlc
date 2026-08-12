from fastapi import HTTPException, status
from sqlalchemy import case
from sqlalchemy.orm import Session

from app.models.iteration import Iteration, IterationProject
from app.models.project import Project
from app.models.workflow_definition import WorkflowState
from app.services.lifecycle_service import project_lifecycle_phase
from app.services.workflow_state_service import initial_system_workflow_values


ACTIVE_ITERATION_CATEGORIES = ("normal", "in_progress")
ELIGIBLE_ITERATION_CATEGORIES = ("start", *ACTIVE_ITERATION_CATEGORIES)


def validate_requirement_iteration(db: Session, project_id: int, iteration_id: int | None) -> int:
    if iteration_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Iteration is required",
        )
    iteration = _active_iteration(db, iteration_id)
    if project_id not in iteration_scoped_project_ids(db, iteration.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Requirement is outside iteration scope",
        )
    if iteration.state_category not in ELIGIBLE_ITERATION_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="需求迭代必须处于未开始或进行中状态",
        )
    return iteration.id


def resolve_work_item_iteration(
    db: Session,
    project_id: int,
    requested_iteration_id: int | None,
    *,
    source_iteration_id: int | None = None,
) -> int:
    if requested_iteration_id is not None:
        iteration = _active_iteration(db, requested_iteration_id)
        if project_id not in iteration_scoped_project_ids(db, iteration.id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Work item is outside iteration scope",
            )
        if iteration.state_category not in ELIGIBLE_ITERATION_CATEGORIES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Closed iteration cannot accept work items",
            )
        return iteration.id
    if source_iteration_id is not None:
        source = (
            db.query(Iteration)
            .filter(Iteration.id == source_iteration_id, Iteration.deleted == 0)
            .first()
        )
        if (
            source is not None
            and source.state_category in ELIGIBLE_ITERATION_CATEGORIES
            and project_id in iteration_scoped_project_ids(db, source.id)
        ):
            return source.id
    existing = eligible_iteration_for_project(db, project_id)
    return existing.id if existing else create_unstarted_iteration(db, project_id).id


def eligible_iteration_for_project(
    db: Session, project_id: int, *, exclude_iteration_id: int | None = None
) -> Iteration | None:
    scoped_membership_project_ids = _project_ancestor_ids(db, project_id)
    query = (
        db.query(Iteration)
        .join(IterationProject, IterationProject.iteration_id == Iteration.id)
        .join(WorkflowState, WorkflowState.id == Iteration.current_state_id)
        .filter(
            Iteration.deleted == 0,
            IterationProject.project_id.in_(scoped_membership_project_ids),
            WorkflowState.category.in_(ELIGIBLE_ITERATION_CATEGORIES),
        )
    )
    if exclude_iteration_id is not None:
        query = query.filter(Iteration.id != exclude_iteration_id)
    return (
        query.order_by(
            case((WorkflowState.category.in_(ACTIVE_ITERATION_CATEGORIES), 0), else_=1),
            Iteration.id.asc(),
        )
        .first()
    )


def fallback_iteration_for_project(
    db: Session, project_id: int, *, exclude_iteration_id: int | None = None
) -> Iteration:
    existing = eligible_iteration_for_project(
        db, project_id, exclude_iteration_id=exclude_iteration_id
    )
    return existing or create_unstarted_iteration(db, project_id)


def eligible_iteration_ids_for_project(db: Session, project_id: int) -> list[int]:
    scoped_membership_project_ids = _project_ancestor_ids(db, project_id)
    return [
        row[0]
        for row in (
            db.query(Iteration.id)
            .join(IterationProject, IterationProject.iteration_id == Iteration.id)
            .join(WorkflowState, WorkflowState.id == Iteration.current_state_id)
            .filter(
                Iteration.deleted == 0,
                IterationProject.project_id.in_(scoped_membership_project_ids),
                WorkflowState.category.in_(ELIGIBLE_ITERATION_CATEGORIES),
            )
            .distinct()
            .all()
        )
    ]


def create_unstarted_iteration(db: Session, project_id: int) -> Iteration:
    project = db.query(Project).filter(Project.id == project_id, Project.deleted == 0).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    iteration = Iteration(
        name="待规划迭代",
        lifecycle_phase=project_lifecycle_phase(db, project_id),
        **initial_system_workflow_values(db, "iteration"),
    )
    db.add(iteration)
    db.flush()
    db.add(IterationProject(iteration_id=iteration.id, project_id=project_id))
    db.flush()
    return iteration


def iteration_scoped_project_ids(db: Session, iteration_id: int) -> set[int]:
    root_ids = [
        row.project_id
        for row in db.query(IterationProject).filter(IterationProject.iteration_id == iteration_id).all()
    ]
    project_ids = set(root_ids)
    for project_id in root_ids:
        project_ids.update(_descendant_project_ids(db, project_id))
    return project_ids


def _active_iteration(db: Session, iteration_id: int) -> Iteration:
    iteration = db.query(Iteration).filter(Iteration.id == iteration_id, Iteration.deleted == 0).first()
    if not iteration:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Iteration not found")
    return iteration


def _descendant_project_ids(db: Session, project_id: int) -> set[int]:
    children = db.query(Project).filter(Project.parent_id == project_id, Project.deleted == 0).all()
    project_ids = {child.id for child in children}
    for child in children:
        project_ids.update(_descendant_project_ids(db, child.id))
    return project_ids


def _project_ancestor_ids(db: Session, project_id: int) -> set[int]:
    project_ids: set[int] = set()
    current_id: int | None = project_id
    while current_id is not None and current_id not in project_ids:
        project_ids.add(current_id)
        current_id = (
            db.query(Project.parent_id)
            .filter(Project.id == current_id, Project.deleted == 0)
            .scalar()
        )
    return project_ids
