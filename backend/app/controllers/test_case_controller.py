from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_optional_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.test_case_import_service import (
    MAX_FILE_BYTES,
    build_test_case_import_template,
    commit_test_case_import,
    inspect_test_case_import,
    parse_import_options,
)
from app.services.project_permission_service import (
    ensure_test_case_execute_permission,
    ensure_test_case_manage_permission,
    ensure_project_view_permission,
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
def get_test_cases(db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_current_user)):
    return list_test_cases(db, current_user)


@router.post("", response_model=TestCaseRead)
def post_test_case(
    payload: TestCaseCreate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_test_case_manage_permission(db, payload.project_id, current_user)
    return create_test_case(db, payload)


@router.get('/import/template')
def download_test_case_import_template(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    content = build_test_case_import_template(db, project_id, current_user)
    return Response(
        content=content,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': 'attachment; filename=test-case-import-template.xlsx'},
    )


async def _import_content(file):
    content = await file.read(MAX_FILE_BYTES + 1)
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(422, '文件不能超过10MB')
    return content


@router.post('/import/preview')
async def preview_test_case_import_file(
    project_id: int = Form(..., gt=0),
    default_requirement_id: int | None = Form(None, gt=0),
    requirement_overrides: str = Form('{}', max_length=200000),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_test_case_manage_permission(db, project_id, current_user)
    return inspect_test_case_import(
        db, project_id, current_user, await _import_content(file), file.filename or '',
        default_requirement_id, parse_import_options(requirement_overrides),
    )


@router.post('/import/commit')
async def commit_test_case_import_file(
    project_id: int = Form(..., gt=0),
    default_requirement_id: int | None = Form(None, gt=0),
    requirement_overrides: str = Form('{}', max_length=200000),
    duplicate_strategy: str = Form('skip'),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_test_case_manage_permission(db, project_id, current_user)
    return commit_test_case_import(
        db, project_id, current_user, await _import_content(file), file.filename or '',
        default_requirement_id, parse_import_options(requirement_overrides), duplicate_strategy,
    )


@router.get("/{test_case_id}", response_model=TestCaseRead)
def get_test_case_detail(test_case_id: int, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_current_user)):
    test_case = get_test_case(db, test_case_id)
    ensure_project_view_permission(db, test_case.project_id, current_user)
    return test_case


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
    if current_user and payload.proposer is None:
        payload.proposer = (current_user.full_name or current_user.username).strip()
    return create_bug_from_test_case(
        db,
        test_case_id,
        payload,
        actor_id=current_user.id if current_user else None,
    )


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
