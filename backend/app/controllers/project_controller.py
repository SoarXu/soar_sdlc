from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_optional_current_user, require_system_admin
from app.db.session import get_db
from app.models.user import User
from app.services.project_permission_service import (
    ensure_audit_view_permission,
    ensure_project_delete_permission,
    ensure_project_manage_permission,
)
from app.services.project_service import (
    activate_project,
    close_project,
    create_project,
    delete_project,
    get_project,
    list_project_audit_logs,
    list_project_bugs_page,
    list_project_iterations_page,
    list_project_members,
    list_project_requirements_page,
    list_project_status_operations,
    list_project_tasks_page,
    list_project_test_cases_page,
    list_project_test_runs_page,
    list_projects,
    replace_project_members,
    start_project,
    suspend_project,
    update_project,
)
from app.views.project_view import (
    ProjectBugPage,
    ProjectCreate,
    ProjectIterationPage,
    ProjectMemberCreate,
    ProjectMemberRead,
    ProjectRead,
    ProjectRequirementPage,
    ProjectTaskPage,
    ProjectTestCasePage,
    ProjectTestRunPage,
    ProjectUpdate,
)
from app.views.audit_log_view import AuditLogRead
from app.views.status_operation_view import StatusOperationCreate, StatusOperationRead


router = APIRouter()


@router.get("", response_model=list[ProjectRead])
def get_projects(
    assignee_rule_config_id: int | None = None,
    db: Session = Depends(get_db),
):
    return list_projects(db, assignee_rule_config_id=assignee_rule_config_id)


@router.get("/{project_id}", response_model=ProjectRead)
def get_project_detail(project_id: int, db: Session = Depends(get_db)):
    return get_project(db, project_id)


@router.get("/{project_id}/members", response_model=list[ProjectMemberRead])
def get_project_members(project_id: int, db: Session = Depends(get_db)):
    return list_project_members(db, project_id)


@router.put("/{project_id}/members", response_model=list[ProjectMemberRead])
def put_project_members(
    project_id: int,
    payload: list[ProjectMemberCreate],
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_project_manage_permission(db, project_id, current_user)
    return replace_project_members(db, project_id, payload)


@router.get("/{project_id}/iterations", response_model=ProjectIterationPage)
def get_project_iterations(
    project_id: int,
    page: int = 1,
    page_size: int = 10,
    keyword: str | None = None,
    status: str | None = None,
    owner_id: int | None = None,
    db: Session = Depends(get_db),
):
    return list_project_iterations_page(db, project_id, page, page_size, keyword, status, owner_id)


@router.get("/{project_id}/requirements", response_model=ProjectRequirementPage)
def get_project_requirements(
    project_id: int,
    page: int = 1,
    page_size: int = 10,
    keyword: str | None = None,
    status: str | None = None,
    owner_id: int | None = None,
    iteration_id: int | None = None,
    db: Session = Depends(get_db),
):
    return list_project_requirements_page(db, project_id, page, page_size, keyword, status, owner_id, iteration_id)


@router.get("/{project_id}/tasks", response_model=ProjectTaskPage)
def get_project_tasks(
    project_id: int,
    page: int = 1,
    page_size: int = 10,
    keyword: str | None = None,
    status: str | None = None,
    owner_id: int | None = None,
    requirement_id: int | None = None,
    db: Session = Depends(get_db),
):
    return list_project_tasks_page(db, project_id, page, page_size, keyword, status, owner_id, requirement_id)


@router.get("/{project_id}/test-cases", response_model=ProjectTestCasePage)
def get_project_test_cases(
    project_id: int,
    page: int = 1,
    page_size: int = 10,
    keyword: str | None = None,
    result: str | None = None,
    requirement_id: int | None = None,
    db: Session = Depends(get_db),
):
    return list_project_test_cases_page(db, project_id, page, page_size, keyword, result, requirement_id)


@router.get("/{project_id}/test-runs", response_model=ProjectTestRunPage)
def get_project_test_runs(
    project_id: int,
    page: int = 1,
    page_size: int = 10,
    keyword: str | None = None,
    status: str | None = None,
    owner_id: int | None = None,
    iteration_id: int | None = None,
    db: Session = Depends(get_db),
):
    return list_project_test_runs_page(db, project_id, page, page_size, keyword, status, owner_id, iteration_id)


@router.get("/{project_id}/bugs", response_model=ProjectBugPage)
def get_project_bugs(
    project_id: int,
    page: int = 1,
    page_size: int = 10,
    keyword: str | None = None,
    status: str | None = None,
    owner_id: int | None = None,
    iteration_id: int | None = None,
    db: Session = Depends(get_db),
):
    return list_project_bugs_page(db, project_id, page, page_size, keyword, status, owner_id, iteration_id)


@router.post("", response_model=ProjectRead)
def post_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_system_admin),
):
    return create_project(db, payload)


@router.patch("/{project_id}", response_model=ProjectRead)
def patch_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_project_manage_permission(db, project_id, current_user)
    return update_project(db, project_id, payload, actor_id=current_user.id if current_user else None)


@router.get("/{project_id}/status-operations", response_model=list[StatusOperationRead])
def get_project_status_operations(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_audit_view_permission(db, project_id, current_user)
    return list_project_status_operations(db, project_id)


@router.get("/{project_id}/audit-logs", response_model=list[AuditLogRead])
def get_project_audit_logs(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_audit_view_permission(db, project_id, current_user)
    return list_project_audit_logs(db, project_id)


@router.post("/{project_id}/start", response_model=ProjectRead)
def start_project_status(
    project_id: int,
    payload: StatusOperationCreate | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_project_manage_permission(db, project_id, current_user)
    return start_project(db, project_id, payload, actor_id=current_user.id if current_user else None)


@router.post("/{project_id}/suspend", response_model=ProjectRead)
def suspend_project_status(
    project_id: int,
    payload: StatusOperationCreate | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_project_manage_permission(db, project_id, current_user)
    return suspend_project(db, project_id, payload, actor_id=current_user.id if current_user else None)


@router.post("/{project_id}/close", response_model=ProjectRead)
def close_project_status(
    project_id: int,
    payload: StatusOperationCreate | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_project_manage_permission(db, project_id, current_user)
    return close_project(db, project_id, payload, actor_id=current_user.id if current_user else None)


@router.post("/{project_id}/activate", response_model=ProjectRead)
def activate_project_status(
    project_id: int,
    payload: StatusOperationCreate | None = None,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_project_manage_permission(db, project_id, current_user)
    return activate_project(db, project_id, payload, actor_id=current_user.id if current_user else None)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_project_delete_permission(db, current_user)
    delete_project(db, project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
