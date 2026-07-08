from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.user import User
from app.services.user_service import authenticate_user, change_password
from app.views.auth_view import ChangePasswordRequest, LoginRequest, TokenResponse


router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.username, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    return TokenResponse(
        access_token=create_access_token(user.username),
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        must_change_password=user.must_change_password,
    )


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def post_change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    change_password(db, current_user, payload.current_password, payload.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
