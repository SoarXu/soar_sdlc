from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_optional_current_user
from app.db.session import get_db
from app.models.user import User
from app.services import work_item_service
from app.views.work_item_view import WorkItemListRead


router = APIRouter()


@router.get("/unassigned", response_model=WorkItemListRead)
def get_unassigned_work_items(
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    return work_item_service.list_unassigned_work_items(db, current_user)
