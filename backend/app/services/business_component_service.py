from fastapi import HTTPException, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.business_component import BusinessComponent, BusinessComponentMember, BusinessComponentTransitionRoute
from app.models.business_component import WorkItemComponent
from app.models.bug import Bug
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.requirement import Requirement
from app.models.task import Task
from app.models.workflow_definition import WorkflowDefinition, WorkflowState, WorkflowTransition
from app.models.assignee_rule_config import AssigneeRuleConfig
from app.models.business_component import WorkflowMigrationLog
from app.services.assignee_rule_config_service import clone_enabled_config
from app.services.workflow_runtime_cache import cached_runtime_value, prime_runtime_values
from app.services.workflow_state_query_service import is_terminal_state
from app.views.business_component_view import (
    BusinessComponentCreateFromProject,
    BusinessComponentMemberWrite,
    BusinessComponentTransitionRouteWrite,
    BusinessComponentUpdate,
)


WORK_ITEM_MODELS = {"requirement": Requirement, "task": Task, "bug": Bug}


def prime_component_runtime_cache(db: Session, items: list[tuple[str, object]], transitions: list[WorkflowTransition], actor_id: int | None) -> None:
    work_items = [(object_type, item) for object_type, item in items if object_type in WORK_ITEM_MODELS]
    if not work_items:
        return
    conditions = [
        and_(WorkItemComponent.object_type == object_type, WorkItemComponent.object_id.in_([item.id for kind, item in work_items if kind == object_type]))
        for object_type in {object_type for object_type, _item in work_items}
    ]
    links = db.query(WorkItemComponent).filter(or_(*conditions)).order_by(WorkItemComponent.id.asc()).all()
    links_by_item = {(object_type, item.id): [] for object_type, item in work_items}
    for link in links:
        links_by_item.setdefault((link.object_type, link.object_id), []).append(link)
    component_ids_by_item = {}
    for key, item_links in links_by_item.items():
        primary_id = next((link.component_id for link in item_links if link.relation_type == "primary"), None)
        component_ids_by_item[key] = primary_id
    prime_runtime_values(db, "work_item_component_ids", {
        key: (primary_id, [link.component_id for link in links_by_item[key] if link.relation_type == "related"])
        for key, primary_id in component_ids_by_item.items()
    })
    component_ids = {component_id for component_id in component_ids_by_item.values() if component_id is not None}
    if not component_ids:
        return
    members = db.query(BusinessComponentMember).filter(
        BusinessComponentMember.component_id.in_(component_ids),
        BusinessComponentMember.enabled.is_(True),
    ).order_by(BusinessComponentMember.id.asc()).all()
    members_by_component = {component_id: [] for component_id in component_ids}
    for member in members:
        members_by_component[member.component_id].append(member)
    prime_runtime_values(db, "component_members", members_by_component)
    if actor_id is not None:
        prime_runtime_values(db, "component_member_roles", {
            (component_id, actor_id): {member.role_id for member in component_members if member.user_id == actor_id}
            for component_id, component_members in members_by_component.items()
        })
    transition_ids = {transition.id for transition in transitions}
    routes = db.query(BusinessComponentTransitionRoute).filter(
        BusinessComponentTransitionRoute.component_id.in_(component_ids),
        BusinessComponentTransitionRoute.transition_id.in_(transition_ids),
        BusinessComponentTransitionRoute.enabled.is_(True),
    ).all()
    route_by_key = {(route.component_id, route.object_type, route.transition_id): route for route in routes}
    route_values = {}
    for object_type, item in work_items:
        component_id = component_ids_by_item[(object_type, item.id)]
        if component_id is None:
            continue
        for transition in transitions:
            key = (component_id, object_type, transition.id)
            route = route_by_key.get(key)
            if not route:
                route_values[key] = None
                continue
            component_members = members_by_component[component_id]
            eligible_ids = _member_ids_for_route(component_members, route.eligible_member_mode, route.eligible_role_ids, route.eligible_user_ids)
            next_owner_ids = _member_ids_for_route(component_members, route.next_owner_mode, route.next_owner_role_ids, None)
            if route.next_owner_mode == "user":
                next_owner_ids = [route.next_owner_user_id] if route.next_owner_user_id in {member.user_id for member in component_members} else []
            route_values[key] = {
                "route_id": route.id,
                "eligible_executor_ids": eligible_ids,
                "eligible_manual_owner_ids": eligible_ids if route.next_owner_mode == "manual" else next_owner_ids,
                "next_owner_id": next_owner_ids[0] if next_owner_ids else None,
                "next_owner_mode": route.next_owner_mode,
                "fallback_mode": route.fallback_mode,
            }
    prime_runtime_values(db, "component_transition_routes", route_values)


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
    target_member_roles = {
        (row.user_id, row.role_id)
        for row in db.query(ProjectMember)
        .filter(ProjectMember.project_id == target_project.id, ProjectMember.user_id.in_(user_ids))
        .all()
    }
    target_member_ids = {user_id for user_id, _ in target_member_roles}
    missing_user_ids = sorted(set(user_ids) - target_member_ids)
    if missing_user_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Component members must belong to the target project", "user_ids": missing_user_ids},
        )

    unassigned_members = [
        {"user_id": item.user_id, "role_id": item.role_id}
        for item in payload
        if (item.user_id, item.role_id) not in target_member_roles
    ]
    if unassigned_members:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "COMPONENT_MEMBER_PROJECT_ROLE_NOT_ASSIGNED",
                "message": "组件成员未被分配所选项目角色",
                "members": unassigned_members,
            },
        )

    db.query(BusinessComponentMember).filter(BusinessComponentMember.component_id == component.id).delete(
        synchronize_session=False
    )
    db.add_all(
        BusinessComponentMember(
            component_id=component.id,
            user_id=item.user_id,
            role_id=item.role_id,
        )
        for item in payload
    )
    db.commit()
    db.expire(component, ["members"])
    return component


def update_business_component(
    db: Session,
    project_id: int,
    component_id: int,
    payload: BusinessComponentUpdate,
) -> BusinessComponent:
    project = _get_project(db, project_id)
    if is_terminal_state(project):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Terminal projects cannot update business components")
    component = _get_component(db, project_id, component_id)
    data = payload.model_dump(exclude_unset=True)
    if "workflow_scheme_id" in data and data["workflow_scheme_id"] is not None:
        scheme = db.query(AssigneeRuleConfig).filter(AssigneeRuleConfig.id == data["workflow_scheme_id"]).first()
        if not scheme or scheme.lifecycle_status != "enabled":
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Workflow scheme must be enabled")
    if "name" in data:
        data["name"] = data["name"].strip()
    for field, value in data.items():
        setattr(component, field, value)
    db.commit()
    db.refresh(component)
    return component


def list_business_component_routes(
    db: Session, project_id: int, component_id: int
) -> list[BusinessComponentTransitionRoute]:
    _get_component(db, project_id, component_id)
    return (
        db.query(BusinessComponentTransitionRoute)
        .filter(BusinessComponentTransitionRoute.component_id == component_id)
        .order_by(BusinessComponentTransitionRoute.object_type, BusinessComponentTransitionRoute.transition_id)
        .all()
    )


def replace_business_component_routes(
    db: Session,
    project_id: int,
    component_id: int,
    payload: list[BusinessComponentTransitionRouteWrite],
) -> list[BusinessComponentTransitionRoute]:
    project = _get_project(db, project_id)
    if is_terminal_state(project):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Terminal projects cannot update business components")
    component = _get_component(db, project_id, component_id)
    route_keys = {(item.object_type, item.transition_id) for item in payload}
    if len(route_keys) != len(payload):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Transition routes must be unique")
    component_role_ids = {
        role_id
        for (role_id,) in db.query(BusinessComponentMember.role_id)
        .filter(BusinessComponentMember.component_id == component.id, BusinessComponentMember.enabled.is_(True))
        .all()
        if role_id is not None
    }
    for item in payload:
        configured_role_ids = set(item.eligible_role_ids) | set(item.next_owner_role_ids)
        if any(role_id <= 0 for role_id in configured_role_ids) or not configured_role_ids.issubset(component_role_ids):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="组件路由角色必须属于已启用组件成员")
        transition = db.query(WorkflowTransition).filter(WorkflowTransition.id == item.transition_id).first()
        definition = (
            db.query(WorkflowDefinition)
            .filter(WorkflowDefinition.id == transition.definition_id)
            .first()
            if transition
            else None
        )
        if not transition or not definition or definition.object_type != item.object_type:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Transition does not match work item type")
        if component.workflow_scheme_id and not _definition_belongs_to_component_scheme(
            transition.definition_id, component.workflow_scheme_id, db
        ):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Transition is outside component workflow scheme")
    db.query(BusinessComponentTransitionRoute).filter(
        BusinessComponentTransitionRoute.component_id == component_id
    ).delete(synchronize_session=False)
    db.add_all(
        BusinessComponentTransitionRoute(component_id=component_id, **item.model_dump())
        for item in payload
    )
    db.commit()
    return list_business_component_routes(db, project_id, component_id)


def resolve_primary_component(db: Session, project_id: int, component_id: int | None) -> BusinessComponent | None:
    if component_id is None:
        return None
    component = _get_component(db, project_id, component_id)
    if not component.enabled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Business component is disabled")
    return component


def replace_work_item_components(
    db: Session,
    object_type: str,
    object_id: int,
    project_id: int,
    primary_component_id: int | None,
    related_component_ids: list[int] | None,
) -> BusinessComponent | None:
    primary = resolve_primary_component(db, project_id, primary_component_id)
    related_ids = related_component_ids or []
    if len(related_ids) != len(set(related_ids)):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Related components must be unique")
    if primary and primary.id in related_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Primary component cannot also be related")
    related_components = [resolve_primary_component(db, project_id, component_id) for component_id in related_ids]
    db.query(WorkItemComponent).filter(
        WorkItemComponent.object_type == object_type,
        WorkItemComponent.object_id == object_id,
    ).delete(synchronize_session=False)
    if primary:
        db.add(
            WorkItemComponent(
                object_type=object_type,
                object_id=object_id,
                component_id=primary.id,
                relation_type="primary",
                component_name_snapshot=primary.name,
            )
        )
    db.add_all(
        WorkItemComponent(
            object_type=object_type,
            object_id=object_id,
            component_id=component.id,
            relation_type="related",
            component_name_snapshot=component.name,
        )
        for component in related_components
    )
    return primary


def attach_work_item_components(db: Session, object_type: str, item) -> None:
    links = (
        db.query(WorkItemComponent, BusinessComponent)
        .join(BusinessComponent, BusinessComponent.id == WorkItemComponent.component_id)
        .filter(WorkItemComponent.object_type == object_type, WorkItemComponent.object_id == item.id)
        .order_by(WorkItemComponent.id.asc())
        .all()
    )
    item.primary_component = next((component for link, component in links if link.relation_type == "primary"), None)
    item.related_components = [component for link, component in links if link.relation_type == "related"]


def work_item_component_ids(db: Session, object_type: str, object_id: int) -> tuple[int | None, list[int]]:
    def load():
        links = (
            db.query(WorkItemComponent)
            .filter(WorkItemComponent.object_type == object_type, WorkItemComponent.object_id == object_id)
            .order_by(WorkItemComponent.id.asc())
            .all()
        )
        primary_id = next((link.component_id for link in links if link.relation_type == "primary"), None)
        related_ids = [link.component_id for link in links if link.relation_type == "related"]
        return primary_id, related_ids

    return cached_runtime_value(db, "work_item_component_ids", (object_type, object_id), load)


def active_primary_component_member_roles(db: Session, object_type: str, item, user_id: int) -> set[int] | None:
    primary_component_id, _ = work_item_component_ids(db, object_type, item.id)
    if primary_component_id is None:
        return None
    return cached_runtime_value(
        db,
        "component_member_roles",
        (primary_component_id, user_id),
        lambda: {
            row.role_id
            for row in db.query(BusinessComponentMember)
            .filter(
                BusinessComponentMember.component_id == primary_component_id,
                BusinessComponentMember.user_id == user_id,
                BusinessComponentMember.enabled.is_(True),
            )
            .all()
            if row.role_id is not None
        },
    )


def active_primary_component_members(
    db: Session, object_type: str, item
) -> list[BusinessComponentMember] | None:
    primary_component_id, _ = work_item_component_ids(db, object_type, item.id)
    if primary_component_id is None:
        return None
    return cached_runtime_value(
        db,
        "component_members",
        primary_component_id,
        lambda: (
            db.query(BusinessComponentMember)
            .filter(
                BusinessComponentMember.component_id == primary_component_id,
                BusinessComponentMember.enabled.is_(True),
            )
            .order_by(BusinessComponentMember.id.asc())
            .all()
        ),
    )


def resolve_component_transition_route(db: Session, object_type: str, item, transition: WorkflowTransition) -> dict | None:
    """Resolve an enabled component-specific route for one work-item transition."""
    primary_component_id, _ = work_item_component_ids(db, object_type, item.id)
    if primary_component_id is None:
        return None
    return cached_runtime_value(
        db,
        "component_transition_routes",
        (primary_component_id, object_type, transition.id),
        lambda: _resolve_component_transition_route(db, primary_component_id, object_type, transition),
    )


def _resolve_component_transition_route(
    db: Session,
    primary_component_id: int,
    object_type: str,
    transition: WorkflowTransition,
) -> dict | None:
    route = (
        db.query(BusinessComponentTransitionRoute)
        .filter(
            BusinessComponentTransitionRoute.component_id == primary_component_id,
            BusinessComponentTransitionRoute.object_type == object_type,
            BusinessComponentTransitionRoute.transition_id == transition.id,
            BusinessComponentTransitionRoute.enabled.is_(True),
        )
        .first()
    )
    if not route:
        return None
    members = (
        db.query(BusinessComponentMember)
        .filter(
            BusinessComponentMember.component_id == primary_component_id,
            BusinessComponentMember.enabled.is_(True),
        )
        .order_by(BusinessComponentMember.id.asc())
        .all()
    )
    eligible_ids = _member_ids_for_route(members, route.eligible_member_mode, route.eligible_role_ids, route.eligible_user_ids)
    next_owner_ids = _member_ids_for_route(members, route.next_owner_mode, route.next_owner_role_ids, None)
    if route.next_owner_mode == "user":
        next_owner_ids = [route.next_owner_user_id] if route.next_owner_user_id in {member.user_id for member in members} else []
    return {
        "route_id": route.id,
        "eligible_executor_ids": eligible_ids,
        "eligible_manual_owner_ids": eligible_ids if route.next_owner_mode == "manual" else next_owner_ids,
        "next_owner_id": next_owner_ids[0] if next_owner_ids else None,
        "next_owner_mode": route.next_owner_mode,
        "fallback_mode": route.fallback_mode,
    }


def _member_ids_for_route(
    members: list[BusinessComponentMember], mode: str, role_ids: list[int] | None, users_value: str | None
) -> list[int]:
    if mode in {"all", "manual"}:
        return sorted({member.user_id for member in members})
    if mode == "users":
        user_ids = _parse_id_csv(users_value)
        return sorted({member.user_id for member in members if member.user_id in user_ids})
    selected_role_ids = set(role_ids or [])
    if not selected_role_ids:
        return sorted({member.user_id for member in members})
    return sorted({member.user_id for member in members if member.role_id in selected_role_ids})


def _split_csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _parse_id_csv(value: str | None) -> set[int]:
    result: set[int] = set()
    for item in _split_csv(value):
        try:
            result.add(int(item))
        except ValueError:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Component route user IDs must be integers")
    return result


def default_primary_component_handler_id(db: Session, object_type: str, item) -> int | None:
    primary_component_id, _ = work_item_component_ids(db, object_type, item.id)
    if primary_component_id is None:
        return None
    member = (
        db.query(BusinessComponentMember)
        .filter(
            BusinessComponentMember.component_id == primary_component_id,
            BusinessComponentMember.enabled.is_(True),
        )
        .order_by(BusinessComponentMember.role_id.asc(), BusinessComponentMember.id.asc())
        .first()
    )
    return member.user_id if member else None


def migrate_work_item_workflow(
    db: Session,
    project_id: int,
    component_id: int,
    object_type: str,
    object_id: int,
    new_definition_id: int,
    new_state_id: int,
    reason: str,
    actor_id: int | None,
):
    component = _get_component(db, project_id, component_id)
    model = WORK_ITEM_MODELS.get(object_type)
    if not model:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported work item type")
    item = db.query(model).filter(model.id == object_id, model.deleted == 0).with_for_update().first()
    if not item or item.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work item not found")
    primary_component_id, _ = work_item_component_ids(db, object_type, item.id)
    if primary_component_id != component.id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Work item does not belong to this primary component")
    definition = (
        db.query(WorkflowDefinition)
        .filter(WorkflowDefinition.id == new_definition_id, WorkflowDefinition.object_type == object_type, WorkflowDefinition.enabled.is_(True))
        .first()
    )
    state = (
        db.query(WorkflowState)
        .filter(WorkflowState.id == new_state_id, WorkflowState.definition_id == new_definition_id, WorkflowState.enabled.is_(True))
        .first()
    )
    if not definition or not state:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Target workflow state is invalid")
    if not component.workflow_scheme_id or not _definition_belongs_to_component_scheme(
        definition.id, component.workflow_scheme_id, db
    ):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Target workflow is outside component scheme")
    if is_terminal_state(item):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Terminal work items cannot migrate workflow")
    old_definition_id, old_state_id = item.workflow_definition_id, item.current_state_id
    item.workflow_definition_id = definition.id
    item.current_state_id = state.id
    db.add(
        WorkflowMigrationLog(
            object_type=object_type,
            object_id=item.id,
            old_definition_id=old_definition_id,
            old_state_id=old_state_id,
            new_definition_id=definition.id,
            new_state_id=state.id,
            reason=reason.strip(),
            actor_id=actor_id,
        )
    )
    db.commit()
    db.refresh(item)
    attach_work_item_components(db, object_type, item)
    return item


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


def _definition_belongs_to_component_scheme(definition_id: int, scheme_id: int, db: Session) -> bool:
    return bool(
        db.query(WorkflowDefinition.id)
        .filter(
            WorkflowDefinition.id == definition_id,
            WorkflowDefinition.scope_type == "assignee_rule_config",
            WorkflowDefinition.scope_id == scheme_id,
            WorkflowDefinition.enabled.is_(True),
        )
        .first()
    )
