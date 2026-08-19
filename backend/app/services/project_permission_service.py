from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.bug import Bug
from app.models.iteration import Iteration, IterationProject
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.requirement import Requirement
from app.models.task import Task
from app.models.test_case import TestCase
from app.models.test_run import TestRun
from app.models.user import User
from app.services.program_permission_service import is_program_governor


SYSTEM_ADMIN_ROLE_KEYS = {"system_admin"}
PROJECT_OWNER_PROJECT_ROLES = {"project_owner"}
TEST_PROJECT_ROLES = {"tester", "test_lead", "qa", "quality_assurance"}


def is_system_admin(db: Session, user_id: int | None) -> bool:
    if user_id is None:
        return False
    return bool(db.query(User.is_system_admin).filter(User.id == user_id, User.deleted == 0).scalar())


def is_project_owner(db: Session, project_id: int | None, user_id: int | None) -> bool:
    if not project_id or user_id is None:
        return False
    project = db.query(Project).filter(Project.id == project_id, Project.deleted == 0).first()
    if project and project.owner_id == user_id:
        return True
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
    return (
        is_system_admin(db, actor.id)
        or is_project_owner(db, project_id, actor.id)
    )


def can_govern_project(db: Session, project_id: int | None, actor: User | None) -> bool:
    if actor is None:
        return False
    project = _get_active_project(db, project_id)
    return (
        can_manage_project(db, project_id, actor)
        or _is_project_owner_ancestor(db, project_id, actor.id)
        or is_program_governor(db, project.program_id if project else None, actor.id)
    )


def can_create_project(db: Session, program_id: int | None, actor: User | None) -> bool:
    if actor is None:
        return False
    return program_id is None or is_program_governor(db, program_id, actor.id)


def can_delete_project(db: Session, project_id: int | None, actor: User | None) -> bool:
    if not can_govern_project(db, project_id, actor):
        return False
    if actor and is_system_admin(db, actor.id):
        return True
    return not _has_active_project_children_or_work_items(db, project_id)


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


def can_view_project_governance_audit(db: Session, project_id: int | None, actor: User | None) -> bool:
    return can_view_audit(db, project_id, actor) or can_govern_project(db, project_id, actor)


def can_view_project_work_items(db: Session, project_id: int | None, actor: User | None) -> bool:
    return can_view_audit(db, project_id, actor)


def can_view_project(db: Session, project_id: int | None, actor: User | None) -> bool:
    return can_view_audit(db, project_id, actor) or can_govern_project(db, project_id, actor)


def visible_project_ids(db: Session, actor: User | None) -> set[int]:
    ensure_authenticated(actor)
    if is_system_admin(db, actor.id):
        return {row.id for row in db.query(Project.id).filter(Project.deleted == 0).all()}
    return {
        project.id
        for project in db.query(Project).filter(Project.deleted == 0).all()
        if can_view_project(db, project.id, actor)
    }


def can_admin_action(db: Session, project_id: int | None, actor_id: int | None) -> bool:
    if actor_id is None:
        return True
    return is_system_admin(db, actor_id) or is_project_owner(db, project_id, actor_id)


def iteration_project_ids(db: Session, iteration_id: int) -> list[int]:
    project_ids = [
        row.project_id
        for row in db.query(IterationProject).filter(IterationProject.iteration_id == iteration_id).all()
    ]
    if project_ids:
        return project_ids
    iteration = db.query(Iteration).filter(Iteration.id == iteration_id, Iteration.deleted == 0).first()
    legacy_project_id = getattr(iteration, "project_id", None) if iteration else None
    return [legacy_project_id] if legacy_project_id else []


def is_iteration_owner(db: Session, iteration_id: int, actor: User | None) -> bool:
    if actor is None:
        return False
    iteration = db.query(Iteration).filter(Iteration.id == iteration_id, Iteration.deleted == 0).first()
    if not iteration or iteration.owner_id != actor.id:
        return False
    project_ids = iteration_project_ids(db, iteration_id)
    if not project_ids:
        return False
    for project_id in project_ids:
        project = _get_active_project(db, project_id)
        if not project or project.state_category == "terminal" or not is_project_member(db, project_id, actor.id):
            return False
    return True


def can_govern_iteration(db: Session, iteration_id: int, actor: User | None) -> bool:
    project_ids = iteration_project_ids(db, iteration_id)
    return bool(project_ids) and all(can_govern_project(db, project_id, actor) for project_id in project_ids)


def can_manage_iteration(db: Session, iteration_id: int, actor: User | None) -> bool:
    return is_iteration_owner(db, iteration_id, actor) or can_govern_iteration(db, iteration_id, actor)


def can_directly_manage_iteration_scope(db: Session, iteration_id: int, actor: User | None) -> bool:
    if is_iteration_owner(db, iteration_id, actor):
        return True
    project_ids = iteration_project_ids(db, iteration_id)
    return bool(project_ids) and all(can_manage_project(db, project_id, actor) for project_id in project_ids)


def can_assign_iteration_owner(db: Session, iteration_id: int, actor: User | None) -> bool:
    if actor is None:
        return False
    project_ids = iteration_project_ids(db, iteration_id)
    return bool(project_ids) and (
        is_system_admin(db, actor.id)
        or all(is_project_owner(db, project_id, actor.id) for project_id in project_ids)
    )


def ensure_iteration_owner_membership(db: Session, owner_id: int | None, project_ids: list[int]) -> None:
    if owner_id is None:
        return
    if not project_ids or any(not is_project_member(db, project_id, owner_id) for project_id in project_ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="请选择当前项目的成员作为迭代负责人",
        )


def ensure_iteration_management_permission(db: Session, iteration_id: int, actor: User | None) -> None:
    ensure_authenticated(actor)
    if not can_manage_iteration(db, iteration_id, actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission to manage iteration delivery")


def ensure_iteration_scope_management_permission(db: Session, iteration_id: int, actor: User | None) -> None:
    ensure_authenticated(actor)
    if not can_directly_manage_iteration_scope(db, iteration_id, actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权调整迭代工作项范围")


def ensure_iteration_owner_assignment_permission(db: Session, iteration_id: int, actor: User | None) -> None:
    ensure_authenticated(actor)
    if not can_assign_iteration_owner(db, iteration_id, actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only project owners or system administrators can change iteration owner")


def ensure_project_manage_permission(db: Session, project_id: int | None, actor: User | None) -> None:
    ensure_authenticated(actor)
    if not can_govern_project(db, project_id, actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权管理项目配置")


def ensure_project_direct_manage_permission(db: Session, project_id: int | None, actor: User | None) -> None:
    ensure_authenticated(actor)
    if not can_manage_project(db, project_id, actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权管理项目业务配置")


def ensure_project_governance_permission(db: Session, project_id: int | None, actor: User | None) -> None:
    ensure_authenticated(actor)
    if not can_govern_project(db, project_id, actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权治理项目")


def ensure_program_governance_permission(db: Session, program_id: int | None, actor: User | None) -> None:
    ensure_authenticated(actor)
    if not is_program_governor(db, program_id, actor.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权治理目标项目集")


def ensure_project_create_permission(db: Session, program_id: int | None, actor: User | None) -> None:
    ensure_authenticated(actor)
    if not can_create_project(db, program_id, actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权创建项目")


def ensure_project_delete_permission(db: Session, project_id: int | None, actor: User | None) -> None:
    ensure_authenticated(actor)
    if not can_delete_project(db, project_id, actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权删除项目")


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


def _is_project_owner_ancestor(db: Session, project_id: int | None, user_id: int | None) -> bool:
    if not project_id or user_id is None:
        return False

    current_project_id = project_id
    visited_project_ids: set[int] = set()
    while current_project_id is not None:
        if current_project_id in visited_project_ids:
            return False
        visited_project_ids.add(current_project_id)
        if is_project_owner(db, current_project_id, user_id):
            return True
        project = _get_active_project(db, current_project_id)
        current_project_id = project.parent_id if project else None
    return False


def _has_active_project_children_or_work_items(db: Session, project_id: int | None) -> bool:
    if not project_id:
        return False
    if db.query(Project.id).filter(Project.parent_id == project_id, Project.deleted == 0).first():
        return True
    for model in (Requirement, Task, TestCase, Bug, TestRun):
        if db.query(model.id).filter(model.project_id == project_id, model.deleted == 0).first():
            return True
    return False


def ensure_workflow_fields_not_updated(fields: set[str]) -> None:
    protected = fields & {"owner_id", "status"}
    if protected:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Workflow-owned fields cannot be updated directly: {', '.join(sorted(protected))}",
        )


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


def ensure_project_governance_audit_view_permission(
    db: Session, project_id: int | None, actor: User | None
) -> None:
    ensure_authenticated(actor)
    if not can_view_project_governance_audit(db, project_id, actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看项目审计历史")


def ensure_project_view_permission(db: Session, project_id: int | None, actor: User | None) -> None:
    ensure_authenticated(actor)
    if not can_view_project(db, project_id, actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看项目数据")


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


def _get_active_project(db: Session, project_id: int | None) -> Project | None:
    if not project_id:
        return None
    return db.query(Project).filter(Project.id == project_id, Project.deleted == 0).first()


def actor_role_keys(db: Session, project_id: int | None, user_id: int | None) -> set[str]:
    if user_id is None:
        return set()
    role_keys = global_role_keys(db, user_id)
    if project_id:
        role_keys.update(
            row.project_role
            for row in db.query(ProjectMember).filter(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
            )
        )
    return role_keys


def global_role_keys(db: Session, user_id: int | None) -> set[str]:
    return {"system_admin"} if is_system_admin(db, user_id) else set()
