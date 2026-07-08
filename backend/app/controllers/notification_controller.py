from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.notification_service import list_notifications
from app.views.notification_view import NotificationRead


router = APIRouter()


@router.get("", response_model=list[NotificationRead])
def get_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_notifications(db, current_user.id)
