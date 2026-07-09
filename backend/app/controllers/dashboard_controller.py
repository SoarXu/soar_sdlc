from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_optional_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.dashboard_service import get_dashboard_summary, get_workbench
from app.views.dashboard_view import DashboardSummary, WorkbenchResponse


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
