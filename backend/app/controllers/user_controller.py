from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import require_system_admin
from app.db.session import get_db
from app.services.role_service import assign_user_roles
from app.services.user_service import create_managed_user, list_users, reset_user_password
from app.views.role_view import UserRoleAssignRequest
from app.views.user_view import UserCreate, UserPasswordResponse, UserRead


router = APIRouter()


@router.get("", response_model=list[UserRead])
def get_users(db: Session = Depends(get_db)):
    return list_users(db)


@router.post("", response_model=UserPasswordResponse, status_code=status.HTTP_201_CREATED)
def post_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_system_admin),
):
    user, initial_password = create_managed_user(db, payload)
    return {"user": list_users(db, user_id=user.id)[0], "initial_password": initial_password}


@router.put("/{user_id}/roles", response_model=UserRead)
def put_user_roles(
    user_id: int,
    payload: UserRoleAssignRequest,
    db: Session = Depends(get_db),
    _admin=Depends(require_system_admin),
):
    user = assign_user_roles(db, user_id, payload.role_ids)
    return list_users(db, user_id=user.id)[0]


@router.post("/{user_id}/reset-password", response_model=UserPasswordResponse)
def post_reset_password(
    user_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(require_system_admin),
):
    user, initial_password = reset_user_password(db, user_id)
    return {"user": list_users(db, user_id=user.id)[0], "initial_password": initial_password}
