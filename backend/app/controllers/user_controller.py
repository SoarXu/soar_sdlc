from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.role_service import assign_user_roles
from app.services.user_service import list_users
from app.views.role_view import UserRoleAssignRequest
from app.views.user_view import UserRead


router = APIRouter()


@router.get("", response_model=list[UserRead])
def get_users(db: Session = Depends(get_db)):
    return list_users(db)


@router.put("/{user_id}/roles", response_model=UserRead)
def put_user_roles(user_id: int, payload: UserRoleAssignRequest, db: Session = Depends(get_db)):
    user = assign_user_roles(db, user_id, payload.role_ids)
    return list_users(db, user_id=user.id)[0]
