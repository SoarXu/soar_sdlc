from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_optional_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.project_permission_service import (
    ensure_audit_view_permission,
    ensure_work_item_create_permission,
    ensure_work_item_delete_permission,
    ensure_project_view_permission,
)
from app.services.task_service import (
    create_linked_task,
    create_task,
    delete_task,
    get_task,
    list_task_audit_logs,
    list_task_children,
    list_task_status_operations,
    list_tasks,
    update_task,
)
from app.views.audit_log_view import AuditLogRead
from app.views.status_operation_view import StatusOperationRead
from app.views.task_view import LinkedTaskCreate, TaskCreate, TaskPageRead, TaskRead, TaskUpdate


router = APIRouter()


@router.get("", response_model=list[TaskRead])
def get_tasks(db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_current_user)):
    return list_tasks(db, current_user)


@router.post("/linked", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def post_linked_task(
    payload: LinkedTaskCreate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    return create_linked_task(db, payload, current_user)


@router.get("/{task_id}", response_model=TaskRead)
def get_task_detail(task_id: int, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_current_user)):
    task = get_task(db, task_id)
    ensure_project_view_permission(db, task.project_id, current_user)
    return task


@router.post("", response_model=TaskRead)
def post_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    if payload.parent_task_id is not None:
        parent = get_task(db, payload.parent_task_id)
        ensure_work_item_create_permission(db, parent.project_id, current_user)
    else:
        ensure_work_item_create_permission(db, payload.project_id, current_user)
    return create_task(db, payload, actor_id=current_user.id if current_user else None)


@router.get("/{task_id}/children", response_model=TaskPageRead)
def get_task_children(
    task_id: int,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    task = get_task(db, task_id)
    ensure_project_view_permission(db, task.project_id, current_user)
    return list_task_children(db, task_id, page, page_size)


@router.patch("/{task_id}", response_model=TaskRead)
def patch_task(
    task_id: int,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    return update_task(db, task_id, payload, actor_id=current_user.id if current_user else None)


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
