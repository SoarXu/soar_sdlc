from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import require_system_admin
from app.db.session import get_db
from app.services import assignee_rule_config_service
from app.views.assignee_rule_config_view import (
    AssigneeRuleConfigCreate,
    AssigneeRuleConfigRead,
    AssigneeRuleConfigUpdate,
    WorkflowTemplateSourceRead,
)


router = APIRouter()


@router.get("", response_model=list[AssigneeRuleConfigRead])
def get_configs(db: Session = Depends(get_db)):
    return assignee_rule_config_service.list_configs(db)


@router.get("/project-options", response_model=list[AssigneeRuleConfigRead])
def get_project_options(db: Session = Depends(get_db)):
    return assignee_rule_config_service.list_project_options(db)


@router.get("/template-sources", response_model=list[WorkflowTemplateSourceRead])
def get_template_sources(db: Session = Depends(get_db)):
    return assignee_rule_config_service.list_template_sources(db)


@router.post("", response_model=AssigneeRuleConfigRead, status_code=status.HTTP_201_CREATED)
def create_config(
    payload: AssigneeRuleConfigCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_system_admin),
):
    return assignee_rule_config_service.create_config(db, payload)


@router.patch("/{config_id}", response_model=AssigneeRuleConfigRead)
def update_config(
    config_id: int,
    payload: AssigneeRuleConfigUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(require_system_admin),
):
    return assignee_rule_config_service.update_config(db, config_id, payload)


@router.post("/{config_id}/enable", response_model=AssigneeRuleConfigRead)
def enable_config(
    config_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(require_system_admin),
):
    return assignee_rule_config_service.enable_config(db, config_id)


@router.post("/{config_id}/disable", response_model=AssigneeRuleConfigRead)
def disable_config(
    config_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(require_system_admin),
):
    return assignee_rule_config_service.disable_config(db, config_id)
