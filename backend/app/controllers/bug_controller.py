from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.bug_service import create_bug, delete_bug, list_bugs, update_bug
from app.views.bug_view import BugCreate, BugRead, BugUpdate


router = APIRouter()


@router.get("", response_model=list[BugRead])
def get_bugs(db: Session = Depends(get_db)):
    return list_bugs(db)


@router.post("", response_model=BugRead)
def post_bug(payload: BugCreate, db: Session = Depends(get_db)):
    return create_bug(db, payload)


@router.patch("/{bug_id}", response_model=BugRead)
def patch_bug(bug_id: int, payload: BugUpdate, db: Session = Depends(get_db)):
    return update_bug(db, bug_id, payload)


@router.delete("/{bug_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_bug(bug_id: int, db: Session = Depends(get_db)):
    delete_bug(db, bug_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
