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
from app.services.bug_service import (
    create_bug,
    delete_bug,
    get_bug,
    list_bug_status_operations,
    list_bugs,
    update_bug,
)
from app.services.validation_case_service import bug_validation_context
from app.views.bug_view import BugCreate, BugRead, BugUpdate
from app.views.status_operation_view import StatusOperationRead
from app.views.test_case_view import BugValidationContextRead


router = APIRouter()


@router.get("", response_model=list[BugRead])
def get_bugs(db: Session = Depends(get_db)):
    return list_bugs(db)


@router.post("", response_model=BugRead)
def post_bug(
    payload: BugCreate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_work_item_create_permission(db, payload.project_id, current_user)
    return create_bug(db, payload, actor_id=current_user.id if current_user else None)


@router.get("/{bug_id}", response_model=BugRead)
def get_bug_detail(bug_id: int, db: Session = Depends(get_db)):
    return get_bug(db, bug_id)


@router.get("/{bug_id}/validation-context", response_model=BugValidationContextRead)
def get_bug_validation_context(bug_id: int, db: Session = Depends(get_db)):
    return bug_validation_context(db, bug_id)


@router.patch("/{bug_id}", response_model=BugRead)
def patch_bug(
    bug_id: int,
    payload: BugUpdate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    return update_bug(db, bug_id, payload, actor_id=current_user.id if current_user else None)


@router.get("/{bug_id}/status-operations", response_model=list[StatusOperationRead])
def get_bug_status_operations(
    bug_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    bug = get_bug(db, bug_id)
    ensure_audit_view_permission(db, bug.project_id, current_user)
    return list_bug_status_operations(db, bug_id)


@router.delete("/{bug_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_bug(
    bug_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    bug = get_bug(db, bug_id)
    ensure_work_item_delete_permission(db, bug.project_id, current_user)
    delete_bug(db, bug_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
