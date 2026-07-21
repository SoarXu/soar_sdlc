from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import require_system_admin
from app.db.session import get_db
from app.services import workflow_definition_service
from app.views.workflow_definition_view import (
    WorkflowDefinitionCreate,
    WorkflowDefinitionRead,
    WorkflowDefinitionUpdate,
    WorkflowGraphRead,
    WorkflowGraphSave,
    WorkflowTemplatePreviewRead,
)


router = APIRouter()


@router.get("", response_model=list[WorkflowDefinitionRead])
def get_workflow_definitions(
    object_type: str | None = None,
    scope_type: str | None = None,
    scope_id: int | None = None,
    db: Session = Depends(get_db),
):
    return workflow_definition_service.list_definitions(
        db,
        object_type=object_type,
        scope_type=scope_type,
        scope_id=scope_id,
    )


@router.post("", response_model=WorkflowDefinitionRead, status_code=status.HTTP_201_CREATED)
def post_workflow_definition(
    payload: WorkflowDefinitionCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_system_admin),
):
    return workflow_definition_service.create_definition(db, payload)


@router.get("/{definition_id}", response_model=WorkflowGraphRead)
def get_workflow_definition_graph(definition_id: int, db: Session = Depends(get_db)):
    return workflow_definition_service.get_graph(db, definition_id)


@router.patch("/{definition_id}", response_model=WorkflowDefinitionRead)
def patch_workflow_definition(
    definition_id: int,
    payload: WorkflowDefinitionUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(require_system_admin),
):
    return workflow_definition_service.update_definition(db, definition_id, payload)


@router.put("/{definition_id}/graph", response_model=WorkflowGraphRead)
def put_workflow_definition_graph(
    definition_id: int,
    payload: WorkflowGraphSave,
    db: Session = Depends(get_db),
    _admin=Depends(require_system_admin),
):
    return workflow_definition_service.save_graph(db, definition_id, payload)


@router.post("/{definition_id}/apply-template", response_model=WorkflowGraphRead)
def post_workflow_definition_template(
    definition_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(require_system_admin),
):
    return workflow_definition_service.apply_template(db, definition_id)


@router.get("/{definition_id}/template-preview", response_model=WorkflowTemplatePreviewRead)
def get_workflow_definition_template_preview(
    definition_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(require_system_admin),
):
    return workflow_definition_service.preview_template(db, definition_id)


@router.delete("/{definition_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workflow_definition(
    definition_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(require_system_admin),
):
    workflow_definition_service.disable_definition(db, definition_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
