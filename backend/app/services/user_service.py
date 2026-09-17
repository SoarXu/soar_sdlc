import secrets
import string
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.services.ldap_auth_service import authenticate_ldap_user
from app.views.auth_view import RegisterRequest
from app.views.user_view import UserCreate, UserUpdate


PASSWORD_SYMBOLS = "!@#$%^&*()-_=+"
PASSWORD_ALPHABET = string.ascii_letters + string.digits + PASSWORD_SYMBOLS


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
                must_change_password=False,
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
        if user.must_change_password:
            user.must_change_password = False
            changed = True
        if changed:
            users.append(user)

    db.commit()
    return db.query(User).filter(User.deleted == 0, User.is_active.is_(True)).order_by(User.id.asc()).all()


def authenticate_user(db: Session, username: str, password: str, ldap_authenticator=None) -> User | None:
    user = db.query(User).filter(User.username == username, User.deleted == 0, User.is_active.is_(True)).first()
    if not user:
        return None
    if user.auth_source == "ldap":
        if not authenticate_ldap_user(db, user, password, authenticator=ldap_authenticator):
            return None
        user.last_login_time = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        db.refresh(user)
    elif not _password_matches(user.password_hash, password):
        return None
    return user


def list_users(db: Session, user_id: int | None = None) -> list[dict]:
    query = db.query(User).filter(User.deleted == 0, User.is_active.is_(True))
    if user_id:
        query = query.filter(User.id == user_id)
    users = query.order_by(User.id.asc()).all()
    return [
        {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name,
            "email": user.email,
            "mobile": user.mobile,
            "department": user.department,
            "employee_no": user.employee_no,
            "auth_source": user.auth_source,
            "is_active": user.is_active,
            "must_change_password": user.must_change_password,
            "is_system_admin": user.is_system_admin,
        }
        for user in users
    ]


def user_display_name(db: Session, user_id: int | None) -> str | None:
    if user_id is None:
        return None
    user = db.query(User).filter(User.id == user_id, User.deleted == 0).first()
    if not user:
        return None
    return (user.full_name or user.username).strip() or None


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
        must_change_password=False,
    )
    db.add(user)
    db.flush()
    db.commit()
    db.refresh(user)
    return user


def create_managed_user(db: Session, payload: UserCreate) -> tuple[User, str]:
    username = payload.username.strip()
    full_name = payload.full_name.strip()
    if not username:
        raise ValueError("Username is required")
    if not full_name:
        raise ValueError("Full name is required")
    if db.query(User).filter(User.username == username, User.deleted == 0).first():
        raise LookupError("Username already exists")
    employee_no = _normalize_employee_no(payload.employee_no)
    _ensure_employee_no_available(db, employee_no)
    initial_password = generate_initial_password()
    user = User(
        username=username,
        full_name=full_name,
        email=payload.email,
        mobile=payload.mobile,
        password_hash=get_password_hash(initial_password),
        department=payload.department,
        employee_no=employee_no,
        auth_source="local",
        is_active=True,
        must_change_password=True,
    )
    db.add(user)
    try:
        db.flush()
        user.is_system_admin = payload.is_system_admin
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if _is_employee_no_conflict(exc):
            raise _employee_no_conflict() from exc
        raise
    db.refresh(user)
    return user, initial_password


def update_managed_user(db: Session, user_id: int, payload: UserUpdate) -> User:
    user = _get_active_user(db, user_id)
    changes = payload.model_dump(exclude_unset=True)
    if "full_name" in changes:
        full_name = (changes["full_name"] or "").strip()
        if not full_name:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Full name is required")
        changes["full_name"] = full_name
    if "employee_no" in changes:
        changes["employee_no"] = _normalize_employee_no(changes["employee_no"])
        _ensure_employee_no_available(db, changes["employee_no"], exclude_user_id=user.id)
    for field, value in changes.items():
        setattr(user, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if _is_employee_no_conflict(exc):
            raise _employee_no_conflict() from exc
        raise
    db.refresh(user)
    return user


def reset_user_password(db: Session, user_id: int) -> tuple[User, str]:
    user = _get_active_user(db, user_id)
    _require_local_password_user(user)
    initial_password = generate_initial_password()
    user.password_hash = get_password_hash(initial_password)
    user.must_change_password = True
    db.commit()
    db.refresh(user)
    return user, initial_password


def change_password(db: Session, user: User, current_password: str, new_password: str) -> None:
    _require_local_password_user(user)
    if not _password_matches(user.password_hash, current_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    if len(new_password) < 8:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Password must be at least 8 characters")
    user.password_hash = get_password_hash(new_password)
    user.must_change_password = False
    db.commit()


def generate_initial_password(length: int = 16) -> str:
    if length < 14:
        raise ValueError("Initial password length must be at least 14")
    random = secrets.SystemRandom()
    required = [
        random.choice(string.ascii_lowercase),
        random.choice(string.ascii_uppercase),
        random.choice(string.digits),
        random.choice(PASSWORD_SYMBOLS),
    ]
    remaining = [random.choice(PASSWORD_ALPHABET) for _ in range(length - len(required))]
    chars = required + remaining
    random.shuffle(chars)
    return "".join(chars)


def get_or_create_demo_user(db: Session) -> User:
    seed_default_users(db)
    return db.query(User).filter(User.username == "admin").one()


def _get_active_user(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id, User.deleted == 0, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _require_local_password_user(user: User) -> None:
    if user.auth_source == "ldap":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="LDAP user password is managed by directory service",
        )


def _normalize_employee_no(employee_no: str | None) -> str | None:
    normalized = employee_no.strip() if employee_no else ""
    return normalized or None


def _ensure_employee_no_available(db: Session, employee_no: str | None, exclude_user_id: int | None = None) -> None:
    if employee_no is None:
        return
    query = db.query(User).filter(User.employee_no == employee_no, User.deleted == 0, User.is_active.is_(True))
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)
    if query.first():
        raise _employee_no_conflict()


def _employee_no_conflict() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": "EMPLOYEE_NO_ALREADY_EXISTS", "message": "工号已被其他用户使用"},
    )


def _is_employee_no_conflict(exc: IntegrityError) -> bool:
    message = str(exc).lower()
    return "uq_users_active_employee_no" in message or "active_employee_no" in message


def _password_matches(password_hash: str, password: str) -> bool:
    try:
        return verify_password(password, password_hash)
    except ValueError:
        return False


