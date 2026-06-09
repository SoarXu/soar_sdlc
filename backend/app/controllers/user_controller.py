from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.services.user_service import get_or_create_demo_user
from app.views.user_view import UserRead


router = APIRouter()


@router.get("", response_model=list[UserRead])
def get_users(db: Session = Depends(get_db)):
    get_or_create_demo_user(db)
    return db.query(User).filter(User.delete_time.is_(None), User.is_active.is_(True)).order_by(User.id.asc()).all()
