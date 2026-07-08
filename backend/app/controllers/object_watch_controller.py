from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.object_watch_service import get_watch_state, unwatch_object, watch_object
from app.views.object_watch_view import ObjectWatchRead, ObjectWatchToggleRequest


router = APIRouter()


@router.get("", response_model=ObjectWatchRead)
def get_object_watch(
    object_type: str,
    object_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_watch_state(db, object_type, object_id, current_user)


@router.post("", response_model=ObjectWatchRead)
def post_object_watch(
    payload: ObjectWatchToggleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return watch_object(db, payload.object_type, payload.object_id, current_user)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_object_watch(
    object_type: str,
    object_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    unwatch_object(db, object_type, object_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
