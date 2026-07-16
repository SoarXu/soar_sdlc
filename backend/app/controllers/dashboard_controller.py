from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_workbench(db, user_id=current_user.id)
