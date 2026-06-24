from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.project_member import ProjectMember


PRODUCT_OWNER_ROLES = ("product_owner", "product_manager")
DEVELOPER_ROLES = ("developer", "tech_lead", "development_lead")
TECH_LEAD_ROLES = ("tech_lead", "development_lead")
TESTER_ROLES = ("tester", "test_lead")


def default_requirement_owner_id(db: Session, project_id: int | None) -> int | None:
    return _default_member_id(db, project_id, PRODUCT_OWNER_ROLES)


def default_developer_id(db: Session, project_id: int | None) -> int | None:
    return _default_member_id(db, project_id, DEVELOPER_ROLES)


def default_tester_id(db: Session, project_id: int | None) -> int | None:
    return _default_member_id(db, project_id, TESTER_ROLES)


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
        .order_by(ProjectMember.is_default_assignee.desc(), ProjectMember.sort_order.asc(), ProjectMember.id.asc())
    )
    if exclude_user_id:
        query = query.filter(ProjectMember.user_id != exclude_user_id)
    member = query.first()
    return member.user_id if member else None
