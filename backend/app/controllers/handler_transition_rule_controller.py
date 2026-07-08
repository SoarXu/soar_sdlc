from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.auth_dependencies import require_system_admin
from app.db.session import get_db
from app.services import handler_transition_rule_service
from app.views.handler_transition_rule_view import (
    HandlerTransitionRuleCreate,
    HandlerTransitionRuleRead,
    HandlerTransitionRuleUpdate,
)


router = APIRouter()


@router.get("", response_model=list[HandlerTransitionRuleRead])
def get_rules(config_id: int | None = None, db: Session = Depends(get_db)):
    return handler_transition_rule_service.list_rules(db, config_id=config_id)


@router.post("", response_model=HandlerTransitionRuleRead, status_code=status.HTTP_201_CREATED)
def create_rule(
    payload: HandlerTransitionRuleCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_system_admin),
):
    return handler_transition_rule_service.create_rule(db, payload)


@router.patch("/{rule_id}", response_model=HandlerTransitionRuleRead)
def update_rule(
    rule_id: int,
    payload: HandlerTransitionRuleUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(require_system_admin),
):
    return handler_transition_rule_service.update_rule(db, rule_id, payload)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(require_system_admin),
):
    handler_transition_rule_service.delete_rule(db, rule_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
