from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.role import Role, RoleCapability
from app.models.user import User
from app.views.role_view import RoleCreate, RoleUpdate


DEFAULT_ROLES = [
    ("department_head", "部门负责人", "负责部门内项目集、项目资源协调和交付治理"),
    ("project_owner", "项目负责人", "管理项目交付"),
    ("product_manager", "产品经理", "维护需求和产品规划"),
    ("development_lead", "开发主管", "负责技术评审和开发协调"),
    ("developer", "开发", "执行任务、修复 Bug"),
    ("tester", "测试", "维护用例、执行测试"),
    ("viewer", "访客", "只读查看项目数据"),
]


def seed_default_roles(db: Session) -> list[Role]:
    for capability, role_name, description in DEFAULT_ROLES:
        binding = db.query(RoleCapability).filter(RoleCapability.capability == capability).first()
        role = db.query(Role).filter(Role.id == binding.role_id).first() if binding else None
        if role is None:
            role = db.query(Role).filter(Role.role_name == role_name).first()
        if not role:
            role = Role(role_name=role_name, description=description, is_system=True, enabled=True)
            db.add(role)
            db.flush()
        if not binding:
            db.add(RoleCapability(capability=capability, role_id=role.id))
    db.commit()
    return list_roles(db)


def list_roles(db: Session) -> list[Role]:
    seed_default_roles_if_needed(db)
    return db.query(Role).order_by(Role.is_system.desc(), Role.id.asc()).all()


def create_role(db: Session, payload: RoleCreate) -> Role:
    role_name = payload.role_name.strip()
    if not role_name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Role name is required")
    if db.query(Role).filter(Role.role_name == role_name).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Role name already exists")
    role = Role(
        role_name=role_name,
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


def set_user_system_admin(db: Session, user_id: int, is_system_admin: bool) -> User:
    user = db.query(User).filter(User.id == user_id, User.deleted == 0).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_system_admin = is_system_admin
    db.commit()
    db.refresh(user)
    return user


def seed_default_roles_if_needed(db: Session) -> None:
    existing = {
        capability
        for (capability,) in db.query(RoleCapability.capability).all()
    }
    if {capability for capability, _, _ in DEFAULT_ROLES}.issubset(existing):
        return
    seed_default_roles(db)


def _get_role(db: Session, role_id: int) -> Role:
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return role
