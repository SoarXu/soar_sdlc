from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.iteration import Iteration, IterationProject
from app.models.project import Project
from app.services.lifecycle_service import project_lifecycle_phase
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


def _raise_pool_integrity_error(project_id: int) -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": POOL_INTEGRITY_ERROR,
            "message": "Project requirement pool integrity check failed",
            "project_id": project_id,
        },
    )
