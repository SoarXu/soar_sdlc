from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_optional_current_user
from app.db.session import get_db
from app.models.iteration import Iteration, IterationProject
from app.models.user import User
from app.services.project_permission_service import (
    can_view_audit,
    ensure_audit_view_permission,
    ensure_iteration_management_permission,
    ensure_iteration_scope_management_permission,
    ensure_iteration_owner_assignment_permission,
    ensure_iteration_owner_membership,
    ensure_project_manage_permission,
    iteration_project_ids,
)
from app.services.iteration_service import (
    available_requirements,
    available_tasks,
    create_iteration,
    delete_iteration,
    defer_work_items,
    ensure_delivery_iteration,
    get_iteration_detail,
    link_bugs,
    link_requirements,
    link_tasks,
    list_iteration_status_operations,
    list_iterations,
    unlink_requirement,
    unlink_task,
    update_iteration,
)
from app.views.status_operation_view import StatusOperationRead
from app.views.iteration_view import (
    DeferIterationWorkItemsRequest,
    DeferIterationWorkItemsResult,
    IterationCreate,
    IterationRead,
    IterationUpdate,
    LinkBugsRequest,
    LinkRequirementsRequest,
    LinkTasksRequest,
)


router = APIRouter()


@router.get("", response_model=list[IterationRead])
def get_iterations(
    project_id: int | None = None,
    db: Session = Depends(get_db),
):
    return list_iterations(db, project_id)


@router.post("", response_model=IterationRead)
def post_iteration(
    payload: IterationCreate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    project_ids = _payload_project_ids(payload)
    _ensure_can_manage_projects(db, project_ids, current_user)
    ensure_iteration_owner_membership(db, payload.owner_id, project_ids)
    return create_iteration(db, payload)


@router.patch("/{iteration_id}", response_model=IterationRead)
def patch_iteration(
    iteration_id: int,
    payload: IterationUpdate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    changed_fields = payload.model_fields_set
    target_project_ids = _payload_project_ids(payload)
    current_project_ids = iteration_project_ids(db, iteration_id)
    if changed_fields & {"project_id", "project_ids", "owner_id", "actual_start_date", "actual_end_date", "lifecycle_phase"}:
        ensure_iteration_owner_assignment_permission(db, iteration_id, current_user)
    else:
        ensure_iteration_management_permission(db, iteration_id, current_user)
    if target_project_ids and changed_fields & {"project_id", "project_ids"}:
        _ensure_can_manage_projects(db, target_project_ids, current_user)
    if "owner_id" in changed_fields:
        ensure_iteration_owner_membership(db, payload.owner_id, target_project_ids or current_project_ids)
    return update_iteration(
        db,
        iteration_id,
        payload,
        actor_id=current_user.id if current_user else None,
    )


@router.get("/{iteration_id}/detail")
def get_iteration_detail_view(
    iteration_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    _ensure_delivery_iteration_operation(db, iteration_id)
    _ensure_can_view_iteration(db, iteration_id, current_user)
    return get_iteration_detail(db, iteration_id)


@router.get("/{iteration_id}/status-operations", response_model=list[StatusOperationRead])
def get_iteration_status_operations(
    iteration_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    _ensure_can_view_iteration_audit(db, iteration_id, current_user)
    return list_iteration_status_operations(db, iteration_id)


@router.post("/{iteration_id}/defer-work-items", response_model=DeferIterationWorkItemsResult)
def defer_iteration_work_items(
    iteration_id: int,
    payload: DeferIterationWorkItemsRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    _ensure_delivery_iteration_operation(db, iteration_id)
    _ensure_delivery_iteration_operation(db, payload.target_iteration_id)
    _ensure_can_manage_iteration_scope(db, iteration_id, current_user)
    _ensure_can_manage_iteration_scope(db, payload.target_iteration_id, current_user)
    return defer_work_items(db, iteration_id, payload, actor_id=current_user.id if current_user else None)


@router.get("/{iteration_id}/available-requirements")
def get_available_requirements(iteration_id: int, db: Session = Depends(get_db)):
    _ensure_delivery_iteration_operation(db, iteration_id)
    return available_requirements(db, iteration_id)


@router.post("/{iteration_id}/requirements")
def post_iteration_requirements(
    iteration_id: int,
    payload: LinkRequirementsRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    _ensure_delivery_iteration_operation(db, iteration_id)
    _ensure_can_manage_iteration_scope(db, iteration_id, current_user)
    return link_requirements(
        db,
        iteration_id,
        payload.requirement_ids,
        actor_id=current_user.id if current_user else None,
    )


@router.delete("/{iteration_id}/requirements/{requirement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_iteration_requirement(
    iteration_id: int,
    requirement_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    _ensure_delivery_iteration_operation(db, iteration_id)
    _ensure_can_manage_iteration_scope(db, iteration_id, current_user)
    unlink_requirement(db, iteration_id, requirement_id, actor_id=current_user.id if current_user else None)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{iteration_id}/available-tasks")
def get_available_tasks(iteration_id: int, db: Session = Depends(get_db)):
    _ensure_delivery_iteration_operation(db, iteration_id)
    return available_tasks(db, iteration_id)


@router.post("/{iteration_id}/tasks")
def post_iteration_tasks(
    iteration_id: int,
    payload: LinkTasksRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    _ensure_delivery_iteration_operation(db, iteration_id)
    _ensure_can_manage_iteration_scope(db, iteration_id, current_user)
    return link_tasks(db, iteration_id, payload.task_ids, actor_id=current_user.id if current_user else None)


@router.post("/{iteration_id}/bugs")
def post_iteration_bugs(
    iteration_id: int,
    payload: LinkBugsRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    _ensure_delivery_iteration_operation(db, iteration_id)
    _ensure_can_manage_iteration_scope(db, iteration_id, current_user)
    return link_bugs(db, iteration_id, payload.bug_ids, actor_id=current_user.id if current_user else None)


@router.delete("/{iteration_id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_iteration_task(
    iteration_id: int,
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    _ensure_delivery_iteration_operation(db, iteration_id)
    _ensure_can_manage_iteration(db, iteration_id, current_user)
    unlink_task(db, iteration_id, task_id, actor_id=current_user.id if current_user else None)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{iteration_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_iteration(
    iteration_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    _ensure_delivery_iteration_operation(db, iteration_id)
    ensure_iteration_owner_assignment_permission(db, iteration_id, current_user)
    delete_iteration(db, iteration_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _payload_project_ids(payload: IterationCreate | IterationUpdate) -> list[int]:
    project_ids = list(payload.project_ids or [])
    if payload.project_id and not project_ids:
        project_ids = [payload.project_id]
    return project_ids


def _ensure_can_manage_projects(db: Session, project_ids: list[int], current_user: User | None) -> None:
    for project_id in project_ids:
        ensure_project_manage_permission(db, project_id, current_user)


def _ensure_can_manage_iteration(db: Session, iteration_id: int, current_user: User | None) -> None:
    ensure_iteration_management_permission(db, iteration_id, current_user)


def _ensure_can_manage_iteration_scope(db: Session, iteration_id: int, current_user: User | None) -> None:
    ensure_iteration_scope_management_permission(db, iteration_id, current_user)


def _ensure_can_view_iteration(db: Session, iteration_id: int, current_user: User | None) -> None:
    project_ids = iteration_project_ids(db, iteration_id)
    if current_user and project_ids and all(can_view_audit(db, project_id, current_user) for project_id in project_ids):
        return
    ensure_iteration_management_permission(db, iteration_id, current_user)


def _ensure_delivery_iteration_operation(db: Session, iteration_id: int) -> None:
    iteration = db.query(Iteration).filter(Iteration.id == iteration_id, Iteration.deleted == 0).first()
    if iteration:
        ensure_delivery_iteration(iteration)


def _ensure_can_view_iteration_audit(db: Session, iteration_id: int, current_user: User | None) -> None:
    project_ids = iteration_project_ids(db, iteration_id)
    if not project_ids:
        ensure_audit_view_permission(db, None, current_user)
    for project_id in project_ids:
        ensure_audit_view_permission(db, project_id, current_user)
