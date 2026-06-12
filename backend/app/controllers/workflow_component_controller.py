from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.workflow_component_service import (
    create_component,
    delete_component,
    list_components,
    list_workflow_handlers,
    update_component,
)
from app.views.workflow_component_view import (
    WorkflowComponentCreate,
    WorkflowComponentRead,
    WorkflowComponentUpdate,
    WorkflowHandlerRead,
)


component_router = APIRouter()
handler_router = APIRouter()


@handler_router.get("", response_model=list[WorkflowHandlerRead])
def get_workflow_handlers():
    return list_workflow_handlers()


@component_router.get("", response_model=list[WorkflowComponentRead])
def get_workflow_components(db: Session = Depends(get_db)):
    return list_components(db)


@component_router.post("", response_model=WorkflowComponentRead)
def post_workflow_component(payload: WorkflowComponentCreate, db: Session = Depends(get_db)):
    return create_component(db, payload)


@component_router.patch("/{component_id}", response_model=WorkflowComponentRead)
def patch_workflow_component(component_id: int, payload: WorkflowComponentUpdate, db: Session = Depends(get_db)):
    return update_component(db, component_id, payload)


@component_router.delete("/{component_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_workflow_component(component_id: int, db: Session = Depends(get_db)):
    delete_component(db, component_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
