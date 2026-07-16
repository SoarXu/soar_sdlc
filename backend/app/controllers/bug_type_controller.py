from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import require_system_admin
from app.db.session import get_db
from app.services import bug_type_service
from app.views.bug_type_view import BugTypeCreate, BugTypeRead, BugTypeUpdate


router = APIRouter()


@router.get("", response_model=list[BugTypeRead])
def get_bug_types(
    include_disabled: bool = Query(False),
    db: Session = Depends(get_db),
):
    return bug_type_service.list_bug_types(db, include_disabled=include_disabled)


@router.post("", response_model=BugTypeRead, status_code=status.HTTP_201_CREATED)
def post_bug_type(
    payload: BugTypeCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_system_admin),
):
    return bug_type_service.create_bug_type(db, payload)


@router.patch("/{bug_type_id}", response_model=BugTypeRead)
def patch_bug_type(
    bug_type_id: int,
    payload: BugTypeUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(require_system_admin),
):
    return bug_type_service.update_bug_type(db, bug_type_id, payload)
