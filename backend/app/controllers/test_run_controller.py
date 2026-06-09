from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.bug_service import create_bug_from_test_run_case
from app.services.test_run_service import (
    create_test_run,
    delete_test_run,
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
def post_test_run(payload: TestRunCreate, db: Session = Depends(get_db)):
    return create_test_run(db, payload)


@router.patch("/test-runs/{test_run_id}", response_model=TestRunRead)
def patch_test_run(test_run_id: int, payload: TestRunUpdate, db: Session = Depends(get_db)):
    return update_test_run(db, test_run_id, payload)


@router.delete("/test-runs/{test_run_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_test_run(test_run_id: int, db: Session = Depends(get_db)):
    delete_test_run(db, test_run_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/test-runs/{test_run_id}/cases", response_model=list[TestRunCaseRead])
def select_cases(test_run_id: int, payload: SelectTestCasesRequest, db: Session = Depends(get_db)):
    return select_test_cases(db, test_run_id, payload)


@router.patch("/test-run-cases/{run_case_id}", response_model=TestRunCaseRead)
def patch_test_run_case(run_case_id: int, payload: TestRunCaseUpdate, db: Session = Depends(get_db)):
    return update_test_run_case(db, run_case_id, payload)


@router.post("/test-run-cases/{run_case_id}/bugs", response_model=BugRead)
def post_bug_from_test_run_case(
    run_case_id: int,
    payload: BugFromTestRunCaseRequest,
    db: Session = Depends(get_db),
):
    return create_bug_from_test_run_case(db, run_case_id, payload)
