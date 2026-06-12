from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.bug_service import (
    activate_bug,
    close_bug,
    create_bug,
    delete_bug,
    get_bug,
    list_bug_status_operations,
    list_bugs,
    resolve_bug,
    start_fixing_bug,
    start_verifying_bug,
    suspend_bug,
    update_bug,
    verify_bug_failed,
    verify_bug_passed,
)
from app.views.bug_view import BugCreate, BugRead, BugStatusActionRequest, BugUpdate
from app.views.status_operation_view import StatusOperationRead


router = APIRouter()


@router.get("", response_model=list[BugRead])
def get_bugs(db: Session = Depends(get_db)):
    return list_bugs(db)


@router.post("", response_model=BugRead)
def post_bug(payload: BugCreate, db: Session = Depends(get_db)):
    return create_bug(db, payload)


@router.get("/{bug_id}", response_model=BugRead)
def get_bug_detail(bug_id: int, db: Session = Depends(get_db)):
    return get_bug(db, bug_id)


@router.patch("/{bug_id}", response_model=BugRead)
def patch_bug(bug_id: int, payload: BugUpdate, db: Session = Depends(get_db)):
    return update_bug(db, bug_id, payload)


@router.post("/{bug_id}/start-fixing", response_model=BugRead)
def start_bug_fixing(bug_id: int, payload: BugStatusActionRequest | None = None, db: Session = Depends(get_db)):
    return start_fixing_bug(db, bug_id, payload)


@router.post("/{bug_id}/resolve", response_model=BugRead)
def post_bug_resolve(bug_id: int, payload: BugStatusActionRequest, db: Session = Depends(get_db)):
    return resolve_bug(db, bug_id, payload)


@router.post("/{bug_id}/start-verifying", response_model=BugRead)
def start_bug_verifying(bug_id: int, payload: BugStatusActionRequest | None = None, db: Session = Depends(get_db)):
    return start_verifying_bug(db, bug_id, payload)


@router.post("/{bug_id}/verify-passed", response_model=BugRead)
def post_bug_verify_passed(bug_id: int, payload: BugStatusActionRequest | None = None, db: Session = Depends(get_db)):
    return verify_bug_passed(db, bug_id, payload)


@router.post("/{bug_id}/verify-failed", response_model=BugRead)
def post_bug_verify_failed(bug_id: int, payload: BugStatusActionRequest | None = None, db: Session = Depends(get_db)):
    return verify_bug_failed(db, bug_id, payload)


@router.post("/{bug_id}/suspend", response_model=BugRead)
def post_bug_suspend(bug_id: int, payload: BugStatusActionRequest | None = None, db: Session = Depends(get_db)):
    return suspend_bug(db, bug_id, payload)


@router.post("/{bug_id}/close", response_model=BugRead)
def post_bug_close(bug_id: int, payload: BugStatusActionRequest | None = None, db: Session = Depends(get_db)):
    return close_bug(db, bug_id, payload)


@router.post("/{bug_id}/activate", response_model=BugRead)
def post_bug_activate(bug_id: int, payload: BugStatusActionRequest | None = None, db: Session = Depends(get_db)):
    return activate_bug(db, bug_id, payload)


@router.get("/{bug_id}/status-operations", response_model=list[StatusOperationRead])
def get_bug_status_operations(bug_id: int, db: Session = Depends(get_db)):
    return list_bug_status_operations(db, bug_id)


@router.delete("/{bug_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_bug(bug_id: int, db: Session = Depends(get_db)):
    delete_bug(db, bug_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
