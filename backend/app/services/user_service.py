from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.models.user import User


DEFAULT_USERS = [
    {
        "username": "admin",
        "full_name": "系统管理员",
        "password": "admin123",
        "department": "系统管理",
    },
    {
        "username": "pm_chen",
        "full_name": "陈序",
        "password": "User123456",
        "department": "项目管理部",
    },
    {
        "username": "rd_lin",
        "full_name": "林航",
        "password": "User123456",
        "department": "研发中心",
    },
    {
        "username": "qa_wang",
        "full_name": "王晴",
        "password": "User123456",
        "department": "测试中心",
    },
    {
        "username": "po_li",
        "full_name": "李澄",
        "password": "User123456",
        "department": "产品部",
    },
]


def seed_default_users(db: Session) -> list[User]:
    users = []
    for item in DEFAULT_USERS:
        user = db.query(User).filter(User.username == item["username"]).first()
        if not user:
            user = User(
                username=item["username"],
                full_name=item["full_name"],
                password_hash=get_password_hash(item["password"]),
                department=item["department"],
                is_active=True,
            )
            db.add(user)
            users.append(user)
            continue

        changed = False
        if user.full_name != item["full_name"]:
            user.full_name = item["full_name"]
            changed = True
        if user.department != item["department"]:
            user.department = item["department"]
            changed = True
        if not _password_matches(user.password_hash, item["password"]):
            user.password_hash = get_password_hash(item["password"])
            changed = True
        if not user.is_active:
            user.is_active = True
            changed = True
        if changed:
            users.append(user)

    db.commit()
    return db.query(User).filter(User.deleted == 0, User.is_active.is_(True)).order_by(User.id.asc()).all()


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    seed_default_users(db)
    user = db.query(User).filter(User.username == username, User.deleted == 0, User.is_active.is_(True)).first()
    if not user or not _password_matches(user.password_hash, password):
        return None
    return user


def get_or_create_demo_user(db: Session) -> User:
    seed_default_users(db)
    return db.query(User).filter(User.username == "admin").one()


def _password_matches(password_hash: str, password: str) -> bool:
    try:
        return verify_password(password, password_hash)
    except ValueError:
        return False
