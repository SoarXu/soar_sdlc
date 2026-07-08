from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import ALGORITHM
from app.db.session import get_db
from app.models.role import Role, UserRole
from app.models.user import User


bearer_scheme = HTTPBearer(auto_error=False)


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    if not credentials:
        return None
    try:
        payload = jwt.decode(credentials.credentials, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        return None
    username = payload.get("sub")
    if not username:
        return None
    return (
        db.query(User)
        .filter(User.username == username, User.deleted == 0, User.is_active.is_(True))
        .first()
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    user = get_optional_current_user(credentials, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def require_system_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    role = (
        db.query(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(
            UserRole.user_id == current_user.id,
            Role.role_key == "system_admin",
            Role.enabled.is_(True),
        )
        .first()
    )
    if not role:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="System administrator role required")
    return current_user
