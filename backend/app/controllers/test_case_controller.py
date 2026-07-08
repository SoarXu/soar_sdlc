from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_optional_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.project_permission_service import (
    ensure_test_case_execute_permission,
    ensure_test_case_manage_permission,
)
from app.services.test_case_service import (
    create_bug_from_test_case,
    create_test_case,
    create_test_case_execution,
    delete_test_case,
    get_test_case,
    list_test_case_executions,
    list_test_cases,
    update_test_case,
)
from app.views.bug_view import BugRead
from app.views.test_case_view import (
    BugFromTestCaseRequest,
    TestCaseCreate,
    TestCaseExecutionCreate,
    TestCaseExecutionRead,
    TestCaseRead,
    TestCaseUpdate,
)


router = APIRouter()


@router.get("", response_model=list[TestCaseRead])
def get_test_cases(db: Session = Depends(get_db)):
    return list_test_cases(db)


@router.post("", response_model=TestCaseRead)
def post_test_case(
    payload: TestCaseCreate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_test_case_manage_permission(db, payload.project_id, current_user)
    return create_test_case(db, payload)


@router.get("/{test_case_id}", response_model=TestCaseRead)
def get_test_case_detail(test_case_id: int, db: Session = Depends(get_db)):
    return get_test_case(db, test_case_id)


@router.patch("/{test_case_id}", response_model=TestCaseRead)
def patch_test_case(
    test_case_id: int,
    payload: TestCaseUpdate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    test_case = get_test_case(db, test_case_id)
    ensure_test_case_manage_permission(db, test_case.project_id, current_user)
    if payload.project_id and payload.project_id != test_case.project_id:
        ensure_test_case_manage_permission(db, payload.project_id, current_user)
    return update_test_case(db, test_case_id, payload)


@router.get("/{test_case_id}/executions", response_model=list[TestCaseExecutionRead])
def get_test_case_executions(test_case_id: int, db: Session = Depends(get_db)):
    return list_test_case_executions(db, test_case_id)


@router.post("/{test_case_id}/executions", response_model=TestCaseExecutionRead)
def post_test_case_execution(
    test_case_id: int,
    payload: TestCaseExecutionCreate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    test_case = get_test_case(db, test_case_id)
    ensure_test_case_execute_permission(db, test_case.project_id, current_user)
    if current_user and payload.executor_id is None:
        payload.executor_id = current_user.id
    return create_test_case_execution(db, test_case_id, payload)


@router.post("/{test_case_id}/bugs", response_model=BugRead)
def post_bug_from_test_case(
    test_case_id: int,
    payload: BugFromTestCaseRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    test_case = get_test_case(db, test_case_id)
    ensure_test_case_execute_permission(db, test_case.project_id, current_user)
    if current_user and payload.reporter_id is None:
        payload.reporter_id = current_user.id
    return create_bug_from_test_case(db, test_case_id, payload)


@router.delete("/{test_case_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_test_case(
    test_case_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    test_case = get_test_case(db, test_case_id)
    ensure_test_case_manage_permission(db, test_case.project_id, current_user)
    delete_test_case(db, test_case_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
