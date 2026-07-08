from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.workflow_rule import WorkflowRule
from app.services.default_workflow_template_service import default_template_summaries
from app.services.workflow_component_service import list_designer_components
from app.views.workflow_view import WorkflowRuleCreate, WorkflowRuleUpdate


def list_workflow_rules(db: Session) -> list[WorkflowRule]:
    return db.query(WorkflowRule).order_by(WorkflowRule.priority.asc(), WorkflowRule.id.desc()).all()


def create_workflow_rule(db: Session, payload: WorkflowRuleCreate) -> WorkflowRule:
    rule = WorkflowRule(**payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def update_workflow_rule(db: Session, rule_id: int, payload: WorkflowRuleUpdate) -> WorkflowRule:
    rule = _get_workflow_rule(db, rule_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    db.commit()
    db.refresh(rule)
    return rule


def delete_workflow_rule(db: Session, rule_id: int) -> None:
    rule = _get_workflow_rule(db, rule_id)
    db.delete(rule)
    db.commit()


def list_workflow_components(db: Session) -> list[dict]:
    return list_designer_components(db)


def list_workflow_templates() -> list[dict]:
    return default_template_summaries()


def _get_workflow_rule(db: Session, rule_id: int) -> WorkflowRule:
    rule = db.query(WorkflowRule).filter(WorkflowRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow rule not found")
    return rule
