from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.role import Role, UserRole
from app.models.user import User
from app.views.role_view import RoleCreate, RoleUpdate


DEFAULT_ROLES = [
    ("system_admin", "系统管理员", "系统初始化、用户、角色、基础配置"),
    ("department_head", "部门负责人", "负责部门内项目集、项目资源协调和交付治理"),
    ("project_owner", "项目负责人", "管理项目交付"),
    ("product_manager", "产品经理", "维护需求和产品规划"),
    ("development_lead", "开发主管", "负责技术评审和开发协调"),
    ("developer", "开发", "执行任务、修复 Bug"),
    ("tester", "测试", "维护用例、执行测试"),
    ("viewer", "访客", "只读查看项目数据"),
]


def seed_default_roles(db: Session) -> list[Role]:
    for role_key, role_name, description in DEFAULT_ROLES:
        role = db.query(Role).filter(Role.role_key == role_key).first()
        if not role:
            db.add(Role(role_key=role_key, role_name=role_name, description=description, is_system=True, enabled=True))
        else:
            role.role_name = role_name
            role.description = description
            role.is_system = True
            role.enabled = True
    db.commit()
    return list_roles(db)


def list_roles(db: Session) -> list[Role]:
    seed_default_roles_if_needed(db)
    return db.query(Role).order_by(Role.is_system.desc(), Role.id.asc()).all()


def create_role(db: Session, payload: RoleCreate) -> Role:
    role_key = payload.role_key.strip()
    if not role_key:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Role key is required")
    if db.query(Role).filter(Role.role_key == role_key).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Role key already exists")
    role = Role(
        role_key=role_key,
        role_name=payload.role_name.strip(),
        description=payload.description,
        is_system=False,
        enabled=payload.enabled,
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


def update_role(db: Session, role_id: int, payload: RoleUpdate) -> Role:
    role = _get_role(db, role_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(role, field, value)
    db.commit()
    db.refresh(role)
    return role


def delete_role(db: Session, role_id: int) -> None:
    role = _get_role(db, role_id)
    role.enabled = False
    role.update_time = datetime.now()
    db.commit()


def assign_user_roles(db: Session, user_id: int, role_ids: list[int]) -> User:
    user = db.query(User).filter(User.id == user_id, User.deleted == 0).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    roles = db.query(Role).filter(Role.id.in_(role_ids), Role.enabled.is_(True)).all() if role_ids else []
    found_ids = {role.id for role in roles}
    missing_ids = set(role_ids) - found_ids
    if missing_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role not found or disabled")
    db.query(UserRole).filter(UserRole.user_id == user_id).delete()
    for role in roles:
        db.add(UserRole(user_id=user_id, role_id=role.id))
    db.commit()
    db.refresh(user)
    return user


def roles_for_users(db: Session, user_ids: list[int]) -> dict[int, list[Role]]:
    if not user_ids:
        return {}
    rows = (
        db.query(UserRole.user_id, Role)
        .join(Role, Role.id == UserRole.role_id)
        .filter(UserRole.user_id.in_(user_ids), Role.enabled.is_(True))
        .order_by(Role.id.asc())
        .all()
    )
    result: dict[int, list[Role]] = {user_id: [] for user_id in user_ids}
    for user_id, role in rows:
        result.setdefault(user_id, []).append(role)
    return result


def seed_default_roles_if_needed(db: Session) -> None:
    existing = {row.role_key for row in db.query(Role.role_key).all()}
    if {role_key for role_key, _, _ in DEFAULT_ROLES}.issubset(existing):
        return
    seed_default_roles(db)


def _get_role(db: Session, role_id: int) -> Role:
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return role
