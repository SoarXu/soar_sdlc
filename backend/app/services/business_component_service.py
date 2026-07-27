from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.business_component import BusinessComponent, BusinessComponentMember
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.services.assignee_rule_config_service import clone_enabled_config
from app.services.workflow_state_query_service import is_terminal_state
from app.views.business_component_view import BusinessComponentCreateFromProject, BusinessComponentMemberWrite


COMPONENT_MEMBER_ROLES = {"owner", "handler", "reviewer", "approver"}


def list_business_components(db: Session, project_id: int) -> list[BusinessComponent]:
    _get_project(db, project_id)
    return (
        db.query(BusinessComponent)
        .filter(BusinessComponent.project_id == project_id)
        .order_by(BusinessComponent.enabled.desc(), BusinessComponent.id.asc())
        .all()
    )


def create_business_component_from_source_project(
    db: Session,
    project_id: int,
    payload: BusinessComponentCreateFromProject,
) -> BusinessComponent:
    target_project = _get_project(db, project_id)
    if is_terminal_state(target_project):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Terminal projects cannot create business components")

    source_project = _get_project(db, payload.source_project_id)
    if not is_terminal_state(source_project):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Source project must be closed")

    existing = (
        db.query(BusinessComponent)
        .filter(
            BusinessComponent.project_id == target_project.id,
            BusinessComponent.source_project_id == source_project.id,
            BusinessComponent.enabled.is_(True),
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Source project already has an active business component")

    component = BusinessComponent(
        project_id=target_project.id,
        source_project_id=source_project.id,
        source_project_name_snapshot=source_project.name,
        name=payload.name.strip(),
        description=payload.description,
        owner_id=target_project.owner_id,
    )
    db.add(component)
    db.flush()
    if source_project.assignee_rule_config_id:
        cloned_scheme = clone_enabled_config(
            db,
            source_project.assignee_rule_config_id,
            f"{component.name}-运维组件方案-{component.id}",
        )
        component.workflow_scheme_id = cloned_scheme.id
    for source_member in (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == source_project.id)
        .order_by(ProjectMember.sort_order.asc(), ProjectMember.id.asc())
        .all()
    ):
        target_member = (
            db.query(ProjectMember)
            .filter(ProjectMember.project_id == target_project.id, ProjectMember.user_id == source_member.user_id)
            .first()
        )
        if not target_member:
            db.add(
                ProjectMember(
                    project_id=target_project.id,
                    user_id=source_member.user_id,
                    project_role=source_member.project_role,
                    is_workbench_participant=source_member.is_workbench_participant,
                    sort_order=source_member.sort_order,
                )
            )
        db.add(
            BusinessComponentMember(
                component_id=component.id,
                user_id=source_member.user_id,
                component_role=_component_role_for_project_role(source_member.project_role),
            )
        )
    db.commit()
    db.refresh(component)
    return component


def replace_business_component_members(
    db: Session,
    project_id: int,
    component_id: int,
    payload: list[BusinessComponentMemberWrite],
) -> BusinessComponent:
    target_project = _get_project(db, project_id)
    if is_terminal_state(target_project):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Terminal projects cannot update business components")
    component = _get_component(db, project_id, component_id)
    user_ids = [item.user_id for item in payload]
    if len(user_ids) != len(set(user_ids)):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Component members must be unique")
    invalid_roles = sorted({item.component_role for item in payload} - COMPONENT_MEMBER_ROLES)
    if invalid_roles:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Unknown component roles", "roles": invalid_roles},
        )
    target_member_ids = {
        row.user_id
        for row in db.query(ProjectMember.user_id)
        .filter(ProjectMember.project_id == target_project.id, ProjectMember.user_id.in_(user_ids))
        .all()
    }
    missing_user_ids = sorted(set(user_ids) - target_member_ids)
    if missing_user_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Component members must belong to the target project", "user_ids": missing_user_ids},
        )

    db.query(BusinessComponentMember).filter(BusinessComponentMember.component_id == component.id).delete(
        synchronize_session=False
    )
    db.add_all(
        BusinessComponentMember(
            component_id=component.id,
            user_id=item.user_id,
            component_role=item.component_role,
        )
        for item in payload
    )
    db.commit()
    db.expire(component, ["members"])
    return component


def _get_project(db: Session, project_id: int) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.deleted == 0).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _get_component(db: Session, project_id: int, component_id: int) -> BusinessComponent:
    component = (
        db.query(BusinessComponent)
        .filter(BusinessComponent.id == component_id, BusinessComponent.project_id == project_id)
        .first()
    )
    if not component:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business component not found")
    return component


def _component_role_for_project_role(project_role: str) -> str:
    normalized = (project_role or "").strip().lower()
    if normalized in {"project_owner", "product_owner", "product_manager"}:
        return "owner"
    if normalized in {"tester", "test_lead", "qa", "quality_assurance"}:
        return "reviewer"
    if normalized in {"approver", "auditor"}:
        return "approver"
    return "handler"
