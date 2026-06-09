from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.models.user import User


def get_or_create_demo_user(db: Session) -> User:
    user = db.query(User).filter(User.username == "admin").first()
    if user:
        if not _password_matches(user.password_hash, "admin123"):
            user.password_hash = get_password_hash("admin123")
            db.commit()
            db.refresh(user)
        return user

    user = User(
        username="admin",
        full_name="系统管理员",
        password_hash=get_password_hash("admin123"),
        department="系统管理",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _password_matches(password_hash: str, password: str) -> bool:
    try:
        return verify_password(password, password_hash)
    except ValueError:
        return False
