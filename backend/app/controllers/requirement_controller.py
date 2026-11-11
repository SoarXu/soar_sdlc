from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status, HTTPException
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_optional_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.project_permission_service import (
    ensure_audit_view_permission,
    ensure_authenticated,
    ensure_work_item_create_permission,
    ensure_work_item_delete_permission,
    ensure_project_view_permission,
)
from app.services.requirement_import_service import (
    build_requirement_import_template,
    commit_requirement_import,
    ensure_excel_filename,
    preview_requirement_import,
    build_requirement_export,
    import_proposer_options,
)
from app.services.requirement_service import (
    create_requirement,
    delete_requirement,
    get_requirement,
    list_requirement_audit_logs,
    list_requirement_status_operations,
    list_requirements,
    update_requirement,
)
from app.services.validation_case_service import requirement_validation_cases
from app.views.requirement_view import (
    RequirementCreate,
    RequirementImportCommitRead,
    RequirementImportPreviewRead,
    RequirementImportDecision,
    RequirementRead,
    RequirementUpdate,
)
from app.views.audit_log_view import AuditLogRead
from app.views.status_operation_view import StatusOperationRead
from app.views.test_case_view import RequirementValidationCasesRead


router = APIRouter()


def _import_decisions(value: str) -> list[dict]:
    try:
        return [item.model_dump() for item in TypeAdapter(list[RequirementImportDecision]).validate_json(value)]
    except ValidationError:
        raise HTTPException(status_code=422, detail='导入行选择格式不正确')


@router.get('/export')
def export_requirements(project_id: int, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_current_user)):
    ensure_authenticated(current_user)
    ensure_project_view_permission(db, project_id, current_user)
    return Response(content=build_requirement_export(db, project_id),
                    media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={'Content-Disposition': 'attachment; filename=requirements.xlsx'})


@router.get('/import/proposers')
def get_import_proposers(q: str = '', db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_current_user)):
    ensure_authenticated(current_user)
    return import_proposer_options(db, q)


@router.get("", response_model=list[RequirementRead])
def get_requirements(db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_current_user)):
    return list_requirements(db, current_user)


@router.get("/import/template")
def download_requirement_import_template(project_id: int | None = None, db: Session = Depends(get_db)):
    content = build_requirement_import_template(db, project_id)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=requirement-import-template.xlsx"},
    )


@router.post("/import/preview", response_model=RequirementImportPreviewRead)
async def preview_requirement_import_file(
    project_id: int | None = Form(None),
    duplicate_strategy: str = Form('update_existing'),
    decisions: str = Form('[]'),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_authenticated(current_user)
    if project_id:
        ensure_work_item_create_permission(db, project_id, current_user)
    ensure_excel_filename(file.filename or "")
    return preview_requirement_import(db, await file.read(), project_id, actor=current_user,
                                     duplicate_strategy=duplicate_strategy, decisions=_import_decisions(decisions))


@router.post("/import/commit", response_model=RequirementImportCommitRead)
async def commit_requirement_import_file(
    duplicate_strategy: str = Form(...),
    preview_token: str = Form(...),
    decisions: str = Form('[]'),
    project_id: int | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_authenticated(current_user)
    if project_id:
        ensure_work_item_create_permission(db, project_id, current_user)
    ensure_excel_filename(file.filename or "")
    return commit_requirement_import(db, await file.read(), duplicate_strategy, project_id, actor=current_user,
                                    decisions=_import_decisions(decisions), preview_token=preview_token)


@router.get("/{requirement_id}", response_model=RequirementRead)
def get_requirement_detail(requirement_id: int, db: Session = Depends(get_db), current_user: User | None = Depends(get_optional_current_user)):
    requirement = get_requirement(db, requirement_id)
    ensure_project_view_permission(db, requirement.project_id, current_user)
    return requirement


@router.get("/{requirement_id}/validation-cases", response_model=RequirementValidationCasesRead)
def get_requirement_validation_cases(requirement_id: int, db: Session = Depends(get_db)):
    return requirement_validation_cases(db, requirement_id)


@router.post("", response_model=RequirementRead)
def post_requirement(
    payload: RequirementCreate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    ensure_work_item_create_permission(db, payload.project_id, current_user)
    return create_requirement(db, payload, actor_id=current_user.id if current_user else None)


@router.patch("/{requirement_id}", response_model=RequirementRead)
def patch_requirement(
    requirement_id: int,
    payload: RequirementUpdate,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    return update_requirement(db, requirement_id, payload, actor_id=current_user.id if current_user else None)


@router.get("/{requirement_id}/status-operations", response_model=list[StatusOperationRead])
def get_requirement_status_operations(
    requirement_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    requirement = get_requirement(db, requirement_id)
    ensure_audit_view_permission(db, requirement.project_id, current_user)
    return list_requirement_status_operations(db, requirement_id)


@router.get("/{requirement_id}/audit-logs", response_model=list[AuditLogRead])
def get_requirement_audit_logs(
    requirement_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    requirement = get_requirement(db, requirement_id)
    ensure_audit_view_permission(db, requirement.project_id, current_user)
    return list_requirement_audit_logs(db, requirement_id)


@router.delete("/{requirement_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_requirement(
    requirement_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    requirement = get_requirement(db, requirement_id)
    ensure_work_item_delete_permission(db, requirement.project_id, current_user)
    delete_requirement(db, requirement_id, actor_id=current_user.id if current_user else None)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
