from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user, require_system_admin
from app.db.session import get_db
from app.services.role_service import set_user_system_admin
from app.services.user_service import create_managed_user, list_users, reset_user_password, update_managed_user
from app.views.user_view import UserCreate, UserPasswordResponse, UserRead, UserSystemAdminUpdate, UserUpdate


router = APIRouter()


@router.get("", response_model=list[UserRead])
def get_users(db: Session = Depends(get_db), _current_user=Depends(get_current_user)):
    return list_users(db)


@router.post("", response_model=UserPasswordResponse, status_code=status.HTTP_201_CREATED)
def post_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_system_admin),
):
    user, initial_password = create_managed_user(db, payload)
    return {"user": list_users(db, user_id=user.id)[0], "initial_password": initial_password}


@router.put("/{user_id}/system-admin", response_model=UserRead)
def put_user_system_admin(
    user_id: int,
    payload: UserSystemAdminUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(require_system_admin),
):
    user = set_user_system_admin(db, user_id, payload.is_system_admin)
    return list_users(db, user_id=user.id)[0]


@router.patch("/{user_id}", response_model=UserRead)
def patch_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(require_system_admin),
):
    user = update_managed_user(db, user_id, payload)
    return list_users(db, user_id=user.id)[0]


@router.post("/{user_id}/reset-password", response_model=UserPasswordResponse)
def post_reset_password(
    user_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(require_system_admin),
):
    user, initial_password = reset_user_password(db, user_id)
    return {"user": list_users(db, user_id=user.id)[0], "initial_password": initial_password}
