from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_optional_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.dashboard_service import get_dashboard_summary, get_workbench, move_workbench_item
from app.views.dashboard_view import DashboardSummary, WorkbenchItem, WorkbenchMoveRequest, WorkbenchResponse


router = APIRouter()


@router.get("/summary", response_model=DashboardSummary)
def summary(db: Session = Depends(get_db)):
    return get_dashboard_summary(db)


@router.get("/workbench", response_model=WorkbenchResponse)
def workbench(
    user_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    return get_workbench(db, user_id=user_id or (current_user.id if current_user else None))


@router.post("/workbench/move", response_model=WorkbenchItem)
def move_workbench(
    payload: WorkbenchMoveRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    return move_workbench_item(db, payload.object_type, payload.object_id, payload.target_iteration_id, current_user)
