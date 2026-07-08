from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_optional_current_user
from app.db.session import get_db
from app.models.user import User
from app.services import workflow_runtime_service
from app.views.workflow_runtime_view import (
    WorkflowTransitionActionRead,
    WorkflowTransitionBatchRead,
    WorkflowTransitionBatchRequest,
    WorkflowTransitionExecuteRead,
    WorkflowTransitionExecuteRequest,
)


router = APIRouter()


@router.get("/{object_type}/{object_id}/transitions", response_model=list[WorkflowTransitionActionRead])
def get_runtime_transitions(
    object_type: str,
    object_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    return workflow_runtime_service.list_available_transitions(db, object_type, object_id, current_user)


@router.post("/transitions/batch", response_model=WorkflowTransitionBatchRead)
def post_runtime_transition_batch(
    payload: WorkflowTransitionBatchRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    return workflow_runtime_service.batch_available_transitions(db, payload, current_user)


@router.post("/{object_type}/{object_id}/transition", response_model=WorkflowTransitionExecuteRead)
def post_runtime_transition(
    object_type: str,
    object_id: int,
    payload: WorkflowTransitionExecuteRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    return workflow_runtime_service.execute_transition(db, object_type, object_id, payload, current_user)
