from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.dashboard_service import get_dashboard_summary
from app.views.dashboard_view import DashboardSummary


router = APIRouter()


@router.get("/summary", response_model=DashboardSummary)
def summary(db: Session = Depends(get_db)):
    return get_dashboard_summary(db)
