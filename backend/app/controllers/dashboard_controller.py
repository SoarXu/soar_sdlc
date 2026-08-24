from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.dashboard_service import get_dashboard_summary, get_workbench, get_workbench_items
from app.views.dashboard_view import DashboardSummary, WorkbenchItemPage, WorkbenchResponse


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


@router.get("/workbench/items", response_model=WorkbenchItemPage)
def workbench_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str | None = None,
    project_ids: list[int] | None = Query(None),
    iteration_ids: list[int] | None = Query(None),
    object_types: list[str] | None = Query(None),
    state_ids: list[int] | None = Query(None),
    priorities: list[str] | None = Query(None),
    handler_ids: list[int] | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_workbench_items(
        db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        keyword=keyword,
        project_ids=project_ids,
        iteration_ids=iteration_ids,
        object_types=object_types,
        state_ids=state_ids,
        priorities=priorities,
        handler_ids=handler_ids,
    )
