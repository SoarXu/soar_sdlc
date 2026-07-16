from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.workflow_definition import WorkflowState, WorkflowTransition


TERMINAL_CATEGORY = "terminal"


def non_terminal_state_clause(model):
    return model.current_state_id.in_(
        select(WorkflowState.id).where(WorkflowState.category != TERMINAL_CATEGORY)
    )


def terminal_state_clause(model):
    return model.current_state_id.in_(
        select(WorkflowState.id).where(WorkflowState.category == TERMINAL_CATEGORY)
    )


def is_terminal_state(item) -> bool:
    state = getattr(item, "current_state", None)
    return bool(state and state.category == TERMINAL_CATEGORY)


def current_state_name(item) -> str | None:
    state = getattr(item, "current_state", None)
    return state.status_name if state else None


def current_state_supports_entry_action(db: Session, item, action_keys: set[str]) -> bool:
    definition_id = getattr(item, "workflow_definition_id", None)
    state_id = getattr(item, "current_state_id", None)
    if not definition_id or not state_id or not action_keys:
        return False
    return db.query(WorkflowTransition.id).filter(
        WorkflowTransition.definition_id == definition_id,
        WorkflowTransition.to_state_id == state_id,
        WorkflowTransition.action_key.in_(action_keys),
        WorkflowTransition.enabled.is_(True),
    ).first() is not None
