from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User


def ensure_local_admin_remains(db: Session, user: User) -> None:
    if not (user.is_system_admin and user.is_active and user.auth_source == "local" and user.deleted == 0):
        return
    local_admins = (
        db.query(User)
        .filter(
            User.deleted == 0,
            User.is_active.is_(True),
            User.is_system_admin.is_(True),
            User.auth_source == "local",
        )
        .with_for_update()
        .all()
    )
    if len(local_admins) <= 1 and any(admin.id == user.id for admin in local_admins):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "LOCAL_ADMIN_REQUIRED", "message": "系统必须保留至少一个启用的本地系统管理员"},
        )
