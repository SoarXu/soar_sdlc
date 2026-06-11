from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.workflow_service import (
    create_workflow_rule,
    delete_workflow_rule,
    list_workflow_components,
    list_workflow_rules,
    list_workflow_templates,
    update_workflow_rule,
)
from app.views.workflow_view import (
    WorkflowComponentRead,
    WorkflowRuleCreate,
    WorkflowRuleRead,
    WorkflowRuleUpdate,
    WorkflowTemplateRead,
)


router = APIRouter()


@router.get("", response_model=list[WorkflowRuleRead])
def get_workflow_rules(db: Session = Depends(get_db)):
    return list_workflow_rules(db)


@router.post("", response_model=WorkflowRuleRead)
def post_workflow_rule(payload: WorkflowRuleCreate, db: Session = Depends(get_db)):
    return create_workflow_rule(db, payload)


@router.get("/components", response_model=list[WorkflowComponentRead])
def get_workflow_components():
    return list_workflow_components()


@router.get("/templates", response_model=list[WorkflowTemplateRead])
def get_workflow_templates():
    return list_workflow_templates()


@router.patch("/{rule_id}", response_model=WorkflowRuleRead)
def patch_workflow_rule(rule_id: int, payload: WorkflowRuleUpdate, db: Session = Depends(get_db)):
    return update_workflow_rule(db, rule_id, payload)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_workflow_rule(rule_id: int, db: Session = Depends(get_db)):
    delete_workflow_rule(db, rule_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
