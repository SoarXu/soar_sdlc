from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.work_item_comment_service import create_comment, list_comments
from app.views.work_item_comment_view import WorkItemCommentCreate, WorkItemCommentListRead, WorkItemCommentRead


router = APIRouter()


@router.get("", response_model=WorkItemCommentListRead)
def get_work_item_comments(
    object_type: str,
    object_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_comments(db, object_type, object_id, current_user)


@router.post("", response_model=WorkItemCommentRead, status_code=status.HTTP_201_CREATED)
def post_work_item_comment(
    payload: WorkItemCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_comment(db, payload, current_user)
