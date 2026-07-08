from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.role import Role, UserRole
from app.models.user import User


SYSTEM_ADMIN_ROLE_KEYS = {"system_admin"}
PROJECT_OWNER_ROLE_KEYS = {"project_owner"}
PROJECT_OWNER_PROJECT_ROLES = {"project_owner"}
TEST_PROJECT_ROLES = {"tester", "test_lead", "qa", "quality_assurance"}


def is_system_admin(db: Session, user_id: int | None) -> bool:
    if user_id is None:
        return False
    return bool(
        db.query(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(
            UserRole.user_id == user_id,
            Role.role_key.in_(SYSTEM_ADMIN_ROLE_KEYS),
            Role.enabled.is_(True),
        )
        .first()
    )


def is_project_owner(db: Session, project_id: int | None, user_id: int | None) -> bool:
    if not project_id or user_id is None:
        return False
    project = db.query(Project).filter(Project.id == project_id, Project.deleted == 0).first()
    if project and project.owner_id == user_id:
        return True
    if _has_role(db, user_id, PROJECT_OWNER_ROLE_KEYS):
        return bool(
            db.query(ProjectMember)
            .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
            .first()
        )
    return bool(
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
            ProjectMember.project_role.in_(PROJECT_OWNER_PROJECT_ROLES),
        )
        .first()
    )


def is_project_member(db: Session, project_id: int | None, user_id: int | None) -> bool:
    if not project_id or user_id is None:
        return False
    return bool(
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
        .first()
    )


def can_manage_project(db: Session, project_id: int | None, actor: User | None) -> bool:
    if actor is None:
        return True
    return is_system_admin(db, actor.id) or is_project_owner(db, project_id, actor.id)


def can_delete_project(db: Session, actor: User | None) -> bool:
    if actor is None:
        return True
    return is_system_admin(db, actor.id)


def can_assign_work_item(db: Session, project_id: int | None, actor: User | None) -> bool:
    if actor is None:
        return True
    return is_system_admin(db, actor.id) or is_project_owner(db, project_id, actor.id)


def can_create_work_item(db: Session, project_id: int | None, actor: User | None) -> bool:
    if actor is None:
        return False
    return (
        is_system_admin(db, actor.id)
        or is_project_owner(db, project_id, actor.id)
        or is_project_member(db, project_id, actor.id)
    )


def can_delete_work_item(db: Session, project_id: int | None, actor: User | None) -> bool:
    if actor is None:
        return False
    return is_system_admin(db, actor.id) or is_project_owner(db, project_id, actor.id)


def can_manage_test_case(db: Session, project_id: int | None, actor: User | None) -> bool:
    if actor is None:
        return False
    return (
        is_system_admin(db, actor.id)
        or is_project_owner(db, project_id, actor.id)
        or _has_project_role(db, project_id, actor.id, TEST_PROJECT_ROLES)
    )


def can_execute_test_case(db: Session, project_id: int | None, actor: User | None) -> bool:
    return can_manage_test_case(db, project_id, actor)


def can_configure_workflow(db: Session, actor: User | None) -> bool:
    if actor is None:
        return False
    return is_system_admin(db, actor.id)


def can_view_audit(db: Session, project_id: int | None, actor: User | None) -> bool:
    if actor is None:
        return False
    return (
        is_system_admin(db, actor.id)
        or is_project_owner(db, project_id, actor.id)
        or is_project_member(db, project_id, actor.id)
    )


def can_admin_action(db: Session, project_id: int | None, actor_id: int | None) -> bool:
    if actor_id is None:
        return True
    return is_system_admin(db, actor_id) or is_project_owner(db, project_id, actor_id)


def ensure_project_manage_permission(db: Session, project_id: int | None, actor: User | None) -> None:
    ensure_authenticated(actor)
    if not can_manage_project(db, project_id, actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权管理项目配置")


def ensure_project_delete_permission(db: Session, actor: User | None) -> None:
    ensure_authenticated(actor)
    if not can_delete_project(db, actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有系统管理员可以删除项目")


def ensure_work_item_assign_permission(db: Session, project_id: int | None, actor: User | None) -> None:
    ensure_authenticated(actor)
    if not can_assign_work_item(db, project_id, actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权指派当前处理人")


def ensure_work_item_action_permission(db: Session, item, actor_id: int | None, object_label: str) -> None:
    if actor_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if getattr(item, "owner_id", None) == actor_id:
        return
    project_id = getattr(item, "source_project_id", None) or getattr(item, "project_id", None)
    if can_admin_action(db, project_id, actor_id):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"只有当前处理人可以操作该{object_label}")


def ensure_authenticated(actor: User | None) -> None:
    if actor is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


def ensure_work_item_create_permission(db: Session, project_id: int | None, actor: User | None) -> None:
    ensure_authenticated(actor)
    if not can_create_work_item(db, project_id, actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权创建工作项")


def ensure_work_item_delete_permission(db: Session, project_id: int | None, actor: User | None) -> None:
    ensure_authenticated(actor)
    if not can_delete_work_item(db, project_id, actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权删除工作项")


def ensure_test_case_manage_permission(db: Session, project_id: int | None, actor: User | None) -> None:
    ensure_authenticated(actor)
    if not can_manage_test_case(db, project_id, actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权管理测试用例")


def ensure_test_case_execute_permission(db: Session, project_id: int | None, actor: User | None) -> None:
    ensure_authenticated(actor)
    if not can_execute_test_case(db, project_id, actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权执行测试用例")


def ensure_workflow_config_permission(db: Session, actor: User | None) -> None:
    ensure_authenticated(actor)
    if not can_configure_workflow(db, actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有系统管理员可以配置工作流")


def ensure_audit_view_permission(db: Session, project_id: int | None, actor: User | None) -> None:
    ensure_authenticated(actor)
    if not can_view_audit(db, project_id, actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看审计历史")


def ensure_project_member(db: Session, project_id: int | None, user_id: int) -> None:
    if not project_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="对象缺少所属项目")
    if is_project_member(db, project_id, user_id):
        return
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="处理人不是对象所属项目成员")


def _has_role(db: Session, user_id: int, role_keys: set[str]) -> bool:
    return bool(
        db.query(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == user_id, Role.role_key.in_(role_keys), Role.enabled.is_(True))
        .first()
    )


def _has_project_role(db: Session, project_id: int | None, user_id: int, project_roles: set[str]) -> bool:
    if not project_id:
        return False
    return bool(
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
            ProjectMember.project_role.in_(project_roles),
        )
        .first()
    )
