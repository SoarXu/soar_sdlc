from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.exception_rule_service import (
    create_exception_rule,
    delete_exception_rule,
    ensure_default_exception_rules,
    update_exception_rule,
)
from app.services.project_permission_service import ensure_workflow_config_permission
from app.views.exception_rule_view import ExceptionRuleCreate, ExceptionRuleRead, ExceptionRuleUpdate


router = APIRouter()


@router.get("", response_model=list[ExceptionRuleRead])
def get_exception_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_workflow_config_permission(db, current_user)
    return ensure_default_exception_rules(db)


@router.post("", response_model=ExceptionRuleRead, status_code=status.HTTP_201_CREATED)
def post_exception_rule(
    payload: ExceptionRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_workflow_config_permission(db, current_user)
    return create_exception_rule(db, payload, current_user.id)


@router.patch("/{rule_id}", response_model=ExceptionRuleRead)
def patch_exception_rule(
    rule_id: int,
    payload: ExceptionRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_workflow_config_permission(db, current_user)
    return update_exception_rule(db, rule_id, payload, current_user.id)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_exception_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_workflow_config_permission(db, current_user)
    delete_exception_rule(db, rule_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
