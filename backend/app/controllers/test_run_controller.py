from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_optional_current_user
from app.db.session import get_db
from app.models.test_run import TestRun, TestRunCase
from app.models.user import User
from app.services.project_permission_service import (
    ensure_test_case_execute_permission,
    ensure_test_case_manage_permission,
)
from app.services.bug_service import create_bug_from_test_run_case
from app.services.test_run_service import (
    create_test_run,
    delete_test_run,
    list_test_run_cases,
    list_test_runs,
    select_test_cases,
    update_test_run,
    update_test_run_case,
)
from app.views.bug_view import BugFromTestRunCaseRequest, BugRead
from app.views.test_run_view import (
    SelectTestCasesRequest,
    TestRunCaseRead,
    TestRunCaseUpdate,
    TestRunCreate,
    TestRunRead,
    TestRunUpdate,
)


router = APIRouter()


@router.get("/test-runs", response_model=list[TestRunRead])
def get_test_runs(db: Session = Depends(get_db)):
    return list_test_runs(db)


@router.post("/test-runs", response_model=TestRunRead)
def post_test_run(
    payload: TestRunCreate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_test_case_manage_permission(db, payload.project_id, current_user)
    return create_test_run(db, payload, actor_id=current_user.id if current_user else None)


@router.patch("/test-runs/{test_run_id}", response_model=TestRunRead)
def patch_test_run(
    test_run_id: int,
    payload: TestRunUpdate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    test_run = _get_test_run(db, test_run_id)
    ensure_test_case_manage_permission(db, test_run.project_id, current_user)
    if payload.project_id and payload.project_id != test_run.project_id:
        ensure_test_case_manage_permission(db, payload.project_id, current_user)
    return update_test_run(db, test_run_id, payload)


@router.delete("/test-runs/{test_run_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_test_run(
    test_run_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    test_run = _get_test_run(db, test_run_id)
    ensure_test_case_manage_permission(db, test_run.project_id, current_user)
    delete_test_run(db, test_run_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/test-runs/{test_run_id}/cases", response_model=list[TestRunCaseRead])
def select_cases(
    test_run_id: int,
    payload: SelectTestCasesRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    test_run = _get_test_run(db, test_run_id)
    ensure_test_case_manage_permission(db, test_run.project_id, current_user)
    return select_test_cases(db, test_run_id, payload)


@router.patch("/test-run-cases/{run_case_id}", response_model=TestRunCaseRead)
def patch_test_run_case(
    run_case_id: int,
    payload: TestRunCaseUpdate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    test_run = _get_test_run_for_case(db, run_case_id)
    ensure_test_case_execute_permission(db, test_run.project_id, current_user)
    if current_user and payload.tester_id is None:
        payload.tester_id = current_user.id
    return update_test_run_case(db, run_case_id, payload)


@router.get("/test-run-cases", response_model=list[TestRunCaseRead])
def get_test_run_cases(db: Session = Depends(get_db)):
    return list_test_run_cases(db)


@router.post("/test-run-cases/{run_case_id}/bugs", response_model=BugRead)
def post_bug_from_test_run_case(
    run_case_id: int,
    payload: BugFromTestRunCaseRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    test_run = _get_test_run_for_case(db, run_case_id)
    ensure_test_case_execute_permission(db, test_run.project_id, current_user)
    if current_user and payload.reporter_id is None:
        payload.reporter_id = current_user.id
    return create_bug_from_test_run_case(
        db,
        run_case_id,
        payload,
        actor_id=current_user.id if current_user else None,
    )


def _get_test_run(db: Session, test_run_id: int) -> TestRun:
    test_run = db.query(TestRun).filter(TestRun.id == test_run_id, TestRun.deleted == 0).first()
    if not test_run:
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test run not found")
    return test_run


def _get_test_run_for_case(db: Session, run_case_id: int) -> TestRun:
    run_case = db.query(TestRunCase).filter(TestRunCase.id == run_case_id).first()
    if not run_case:
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test run case not found")
    return _get_test_run(db, run_case.test_run_id)
