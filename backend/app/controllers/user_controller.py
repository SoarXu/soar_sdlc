from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.user_service import seed_default_users
from app.views.user_view import UserRead


router = APIRouter()


@router.get("", response_model=list[UserRead])
def get_users(db: Session = Depends(get_db)):
    return seed_default_users(db)
