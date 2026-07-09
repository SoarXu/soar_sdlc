from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_optional_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.project_permission_service import (
    ensure_audit_view_permission,
    ensure_work_item_create_permission,
    ensure_work_item_delete_permission,
)
from app.services.task_service import (
    create_task,
    delete_task,
    get_task,
    list_task_audit_logs,
    list_task_status_operations,
    list_tasks,
    update_task,
)
from app.services.assignment_service import assign_task_owner, batch_assign_task_owner
from app.views.audit_log_view import AuditLogRead
from app.views.status_operation_view import AssignOwnerRequest, BatchAssignOwnerRead, BatchAssignOwnerRequest, StatusOperationRead
from app.views.task_view import TaskCreate, TaskRead, TaskUpdate


router = APIRouter()


@router.get("", response_model=list[TaskRead])
def get_tasks(db: Session = Depends(get_db)):
    return list_tasks(db)


@router.get("/{task_id}", response_model=TaskRead)
def get_task_detail(task_id: int, db: Session = Depends(get_db)):
    return get_task(db, task_id)


@router.post("", response_model=TaskRead)
def post_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_work_item_create_permission(db, payload.project_id, current_user)
    return create_task(db, payload)


@router.post("/batch-assign", response_model=BatchAssignOwnerRead)
def batch_assign_tasks(
    payload: BatchAssignOwnerRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    return batch_assign_task_owner(db, payload, actor=current_user)


@router.patch("/{task_id}", response_model=TaskRead)
def patch_task(
    task_id: int,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    return update_task(db, task_id, payload, actor_id=current_user.id if current_user else None)


@router.post("/{task_id}/assign", response_model=TaskRead)
def assign_task(
    task_id: int,
    payload: AssignOwnerRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    return assign_task_owner(db, task_id, payload, actor=current_user)


@router.get("/{task_id}/status-operations", response_model=list[StatusOperationRead])
def get_task_status_operations(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    task = get_task(db, task_id)
    ensure_audit_view_permission(db, task.project_id, current_user)
    return list_task_status_operations(db, task_id)


@router.get("/{task_id}/audit-logs", response_model=list[AuditLogRead])
def get_task_audit_logs(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    task = get_task(db, task_id)
    ensure_audit_view_permission(db, task.project_id, current_user)
    return list_task_audit_logs(db, task_id)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    task = get_task(db, task_id)
    ensure_work_item_delete_permission(db, task.project_id, current_user)
    delete_task(db, task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
