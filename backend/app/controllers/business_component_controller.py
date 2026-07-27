from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_optional_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.business_component_service import (
    create_business_component_from_source_project,
    list_business_components,
    list_business_component_routes,
    migrate_work_item_workflow,
    replace_business_component_members,
    replace_business_component_routes,
    update_business_component,
)
from app.services.project_permission_service import ensure_project_manage_permission
from app.views.business_component_view import (
    BusinessComponentCreateFromProject,
    BusinessComponentMemberWrite,
    BusinessComponentRead,
    BusinessComponentTransitionRouteWrite,
    BusinessComponentUpdate,
    WorkflowMigrationRequest,
)


router = APIRouter()


@router.get("/{project_id}/business-components", response_model=list[BusinessComponentRead])
def get_business_components(project_id: int, db: Session = Depends(get_db)):
    return list_business_components(db, project_id)


@router.post(
    "/{project_id}/business-components/from-project",
    response_model=BusinessComponentRead,
    status_code=status.HTTP_201_CREATED,
)
def post_business_component_from_project(
    project_id: int,
    payload: BusinessComponentCreateFromProject,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_project_manage_permission(db, project_id, current_user)
    return create_business_component_from_source_project(db, project_id, payload)


@router.put("/{project_id}/business-components/{component_id}/members", response_model=BusinessComponentRead)
def put_business_component_members(
    project_id: int,
    component_id: int,
    payload: list[BusinessComponentMemberWrite],
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_project_manage_permission(db, project_id, current_user)
    return replace_business_component_members(db, project_id, component_id, payload)


@router.patch("/{project_id}/business-components/{component_id}", response_model=BusinessComponentRead)
def patch_business_component(
    project_id: int,
    component_id: int,
    payload: BusinessComponentUpdate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_project_manage_permission(db, project_id, current_user)
    return update_business_component(db, project_id, component_id, payload)


@router.get("/{project_id}/business-components/{component_id}/transition-routes")
def get_business_component_routes(
    project_id: int,
    component_id: int,
    db: Session = Depends(get_db),
):
    return list_business_component_routes(db, project_id, component_id)


@router.put("/{project_id}/business-components/{component_id}/transition-routes")
def put_business_component_routes(
    project_id: int,
    component_id: int,
    payload: list[BusinessComponentTransitionRouteWrite],
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_project_manage_permission(db, project_id, current_user)
    return replace_business_component_routes(db, project_id, component_id, payload)


@router.post("/{project_id}/business-components/{component_id}/work-items/{object_type}/{object_id}/workflow-migrations")
def post_workflow_migration(
    project_id: int,
    component_id: int,
    object_type: str,
    object_id: int,
    payload: WorkflowMigrationRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_project_manage_permission(db, project_id, current_user)
    item = migrate_work_item_workflow(
        db,
        project_id,
        component_id,
        object_type,
        object_id,
        payload.new_definition_id,
        payload.new_state_id,
        payload.reason,
        current_user.id if current_user else None,
    )
    return {"id": item.id, "workflow_definition_id": item.workflow_definition_id, "current_state_id": item.current_state_id}
