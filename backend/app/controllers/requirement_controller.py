from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.requirement_service import (
    activate_requirement,
    close_requirement,
    create_requirement,
    delete_requirement,
    generate_task_from_requirement,
    get_requirement,
    list_requirement_audit_logs,
    list_requirement_status_operations,
    list_requirements,
    update_requirement,
)
from app.views.requirement_view import GenerateTaskRequest, RequirementCreate, RequirementRead, RequirementUpdate
from app.views.audit_log_view import AuditLogRead
from app.views.status_operation_view import StatusOperationCreate, StatusOperationRead
from app.views.task_view import TaskRead


router = APIRouter()


@router.get("", response_model=list[RequirementRead])
def get_requirements(db: Session = Depends(get_db)):
    return list_requirements(db)


@router.get("/{requirement_id}", response_model=RequirementRead)
def get_requirement_detail(requirement_id: int, db: Session = Depends(get_db)):
    return get_requirement(db, requirement_id)


@router.post("", response_model=RequirementRead)
def post_requirement(payload: RequirementCreate, db: Session = Depends(get_db)):
    return create_requirement(db, payload)


@router.patch("/{requirement_id}", response_model=RequirementRead)
def patch_requirement(requirement_id: int, payload: RequirementUpdate, db: Session = Depends(get_db)):
    return update_requirement(db, requirement_id, payload)


@router.post("/{requirement_id}/activate", response_model=RequirementRead)
def activate_requirement_status(requirement_id: int, db: Session = Depends(get_db)):
    return activate_requirement(db, requirement_id)


@router.post("/{requirement_id}/close", response_model=RequirementRead)
def close_requirement_status(requirement_id: int, payload: StatusOperationCreate, db: Session = Depends(get_db)):
    return close_requirement(db, requirement_id, payload)


@router.get("/{requirement_id}/status-operations", response_model=list[StatusOperationRead])
def get_requirement_status_operations(requirement_id: int, db: Session = Depends(get_db)):
    return list_requirement_status_operations(db, requirement_id)


@router.get("/{requirement_id}/audit-logs", response_model=list[AuditLogRead])
def get_requirement_audit_logs(requirement_id: int, db: Session = Depends(get_db)):
    return list_requirement_audit_logs(db, requirement_id)


@router.delete("/{requirement_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_requirement(requirement_id: int, db: Session = Depends(get_db)):
    delete_requirement(db, requirement_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{requirement_id}/generate-task", response_model=TaskRead)
def generate_task(requirement_id: int, payload: GenerateTaskRequest, db: Session = Depends(get_db)):
    return generate_task_from_requirement(db, requirement_id, payload)
