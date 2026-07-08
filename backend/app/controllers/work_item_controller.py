from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_optional_current_user
from app.db.session import get_db
from app.models.user import User
from app.services import work_item_service
from app.views.work_item_view import (
    WorkItemAssignRequest,
    WorkItemAutoAssignRequest,
    WorkItemBatchAssignRequest,
    WorkItemBatchResult,
    WorkItemClaimRequest,
    WorkItemListRead,
)


router = APIRouter()


@router.get("/unassigned", response_model=WorkItemListRead)
def get_unassigned_work_items(db: Session = Depends(get_db)):
    return work_item_service.list_unassigned_work_items(db)


@router.post("/{object_type}/{object_id}/claim")
def claim_work_item(
    object_type: str,
    object_id: int,
    payload: WorkItemClaimRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    return work_item_service.claim_work_item(db, object_type, object_id, payload or WorkItemClaimRequest(), current_user)


@router.post("/{object_type}/{object_id}/assign")
def assign_work_item(
    object_type: str,
    object_id: int,
    payload: WorkItemAssignRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    return work_item_service.assign_work_item(db, object_type, object_id, payload, current_user)


@router.post("/batch-assign", response_model=WorkItemBatchResult)
def batch_assign_work_items(
    payload: WorkItemBatchAssignRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    return work_item_service.batch_assign_work_items(db, payload, current_user)


@router.post("/unassigned/auto-assign", response_model=WorkItemBatchResult)
def auto_assign_work_items(
    payload: WorkItemAutoAssignRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    return work_item_service.auto_assign_unassigned_work_items(db, payload, current_user)
