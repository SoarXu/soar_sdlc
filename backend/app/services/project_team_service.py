from sqlalchemy.orm import Session

from app.models.assignee_rule_config import AssigneeRuleConfig
from app.models.project import Project
from app.models.project_member import ProjectMember


PRODUCT_OWNER_ROLES = ("product_owner", "product_manager")
DEVELOPER_ROLES = ("developer", "tech_lead", "development_lead")
TECH_LEAD_ROLES = ("tech_lead", "development_lead")
TESTER_ROLES = ("tester", "test_lead")


def default_requirement_owner_id(db: Session, project_id: int | None) -> int | None:
    return _configured_default_member_id(db, project_id, "requirement_owner_roles")


def default_developer_id(db: Session, project_id: int | None) -> int | None:
    return _configured_default_member_id(db, project_id, "task_owner_roles")


def default_tester_id(db: Session, project_id: int | None) -> int | None:
    return _configured_default_member_id(db, project_id, "test_case_tester_roles")


def default_bug_owner_id(db: Session, project_id: int | None) -> int | None:
    return _configured_default_member_id(db, project_id, "bug_owner_roles")


def default_test_run_owner_id(db: Session, project_id: int | None) -> int | None:
    return _configured_default_member_id(db, project_id, "test_run_owner_roles")


def default_tech_lead_id(db: Session, project_id: int | None, exclude_user_id: int | None = None) -> int | None:
    return _default_member_id(db, project_id, TECH_LEAD_ROLES, exclude_user_id=exclude_user_id)


def workbench_project_ids_for_user(db: Session, user_id: int | None) -> set[int]:
    if not user_id:
        return set()
    member_project_ids = {
        row.project_id
        for row in db.query(ProjectMember.project_id)
        .filter(ProjectMember.user_id == user_id, ProjectMember.is_workbench_participant == True)  # noqa: E712
        .all()
    }
    owned_project_ids = {
        row.id for row in db.query(Project.id).filter(Project.owner_id == user_id, Project.deleted == 0).all()
    }
    return member_project_ids | owned_project_ids


def _default_member_id(
    db: Session,
    project_id: int | None,
    roles: tuple[str, ...],
    exclude_user_id: int | None = None,
) -> int | None:
    if not project_id:
        return None
    query = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.project_role.in_(roles))
        .order_by(ProjectMember.sort_order.asc(), ProjectMember.id.asc())
    )
    if exclude_user_id:
        query = query.filter(ProjectMember.user_id != exclude_user_id)
    member = query.first()
    return member.user_id if member else None


def _configured_default_member_id(
    db: Session,
    project_id: int | None,
    config_field: str,
) -> int | None:
    configured_roles = _configured_roles(db, project_id, config_field)
    for role in configured_roles:
        configured_member_id = _default_member_id(db, project_id, (role,))
        if configured_member_id:
            return configured_member_id
    return None


def _configured_roles(db: Session, project_id: int | None, config_field: str) -> tuple[str, ...]:
    if not project_id:
        return ()
    project = (
        db.query(Project.assignee_rule_config_id)
        .filter(Project.id == project_id, Project.deleted == 0)
        .first()
    )
    if not project or not project.assignee_rule_config_id:
        return ()
    config = (
        db.query(AssigneeRuleConfig)
        .filter(AssigneeRuleConfig.id == project.assignee_rule_config_id, AssigneeRuleConfig.enabled == True)  # noqa: E712
        .first()
    )
    if not config:
        return ()
    value = getattr(config, config_field, "") or ""
    return tuple(item.strip() for item in value.split(",") if item.strip())
