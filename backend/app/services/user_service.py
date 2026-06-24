from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.models.role import Role, UserRole
from app.models.user import User
from app.views.auth_view import RegisterRequest


DEFAULT_USERS = [
    {
        "username": "admin",
        "full_name": "Admin",
        "password": "admin123",
        "department": "System",
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
    user = db.query(User).filter(User.username == username, User.deleted == 0, User.is_active.is_(True)).first()
    if not user or not _password_matches(user.password_hash, password):
        return None
    return user


def list_users(db: Session, user_id: int | None = None) -> list[dict]:
    query = db.query(User).filter(User.deleted == 0, User.is_active.is_(True))
    if user_id:
        query = query.filter(User.id == user_id)
    users = query.order_by(User.id.asc()).all()
    role_map = _roles_for_users(db, [user.id for user in users])
    return [
        {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "email": user.email,
            "mobile": user.mobile,
            "department": user.department,
            "is_active": user.is_active,
            "roles": role_map.get(user.id, []),
        }
        for user in users
    ]


def register_user(db: Session, payload: RegisterRequest) -> User:
    username = payload.username.strip()
    full_name = payload.full_name.strip()
    password = payload.password
    if not username:
        raise ValueError("Username is required")
    if not full_name:
        raise ValueError("Full name is required")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters")
    existing = db.query(User).filter(User.username == username, User.deleted == 0).first()
    if existing:
        raise LookupError("Username already exists")
    user = User(
        username=username,
        full_name=full_name,
        email=payload.email,
        mobile=payload.mobile,
        password_hash=get_password_hash(password),
        department=payload.department,
        is_active=True,
    )
    db.add(user)
    db.flush()
    developer_role = db.query(Role).filter(Role.role_key == "developer", Role.enabled.is_(True)).first()
    if developer_role:
        db.add(UserRole(user_id=user.id, role_id=developer_role.id))
    db.commit()
    db.refresh(user)
    return user


def get_or_create_demo_user(db: Session) -> User:
    seed_default_users(db)
    return db.query(User).filter(User.username == "admin").one()


def _password_matches(password_hash: str, password: str) -> bool:
    try:
        return verify_password(password, password_hash)
    except ValueError:
        return False


def _roles_for_users(db: Session, user_ids: list[int]) -> dict[int, list[dict]]:
    if not user_ids:
        return {}
    rows = (
        db.query(UserRole.user_id, Role)
        .join(Role, Role.id == UserRole.role_id)
        .filter(UserRole.user_id.in_(user_ids), Role.enabled.is_(True))
        .order_by(Role.id.asc())
        .all()
    )
    result: dict[int, list[dict]] = {user_id: [] for user_id in user_ids}
    for user_id, role in rows:
        result.setdefault(user_id, []).append(
            {
                "id": role.id,
                "role_key": role.role_key,
                "role_name": role.role_name,
                "description": role.description,
                "is_system": role.is_system,
                "enabled": role.enabled,
                "create_time": role.create_time,
                "update_time": role.update_time,
            }
        )
    return result
