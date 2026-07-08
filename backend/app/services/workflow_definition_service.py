from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.assignee_rule_config import AssigneeRuleConfig
from app.models.handler_transition_rule import HandlerTransitionRule
from app.models.workflow_definition import WorkflowDefinition, WorkflowState, WorkflowTransition
from app.views.workflow_definition_view import (
    WorkflowDefinitionCreate,
    WorkflowDefinitionUpdate,
    WorkflowGraphSave,
    WorkflowStateBase,
    WorkflowTransitionBase,
)


OBJECT_TYPES = {"requirement", "task", "bug"}
SCOPE_TYPES = {"system", "project", "assignee_rule_config"}
STATE_CATEGORIES = {"start", "normal", "terminal"}


def list_definitions(
    db: Session,
    object_type: str | None = None,
    scope_type: str | None = None,
    scope_id: int | None = None,
) -> list[WorkflowDefinition]:
    query = db.query(WorkflowDefinition)
    if object_type:
        query = query.filter(WorkflowDefinition.object_type == object_type)
    if scope_type:
        query = query.filter(WorkflowDefinition.scope_type == scope_type)
    if scope_id is not None:
        query = query.filter(WorkflowDefinition.scope_id == scope_id)
    return query.order_by(WorkflowDefinition.id.desc()).all()


def create_definition(db: Session, payload: WorkflowDefinitionCreate) -> WorkflowDefinition:
    _validate_definition_payload(db, payload.model_dump())
    definition = WorkflowDefinition(**payload.model_dump())
    db.add(definition)
    db.commit()
    db.refresh(definition)
    return definition


def update_definition(db: Session, definition_id: int, payload: WorkflowDefinitionUpdate) -> WorkflowDefinition:
    definition = _get_definition(db, definition_id)
    data = payload.model_dump(exclude_unset=True)
    merged = {
        "name": definition.name,
        "object_type": definition.object_type,
        "scope_type": definition.scope_type,
        "scope_id": definition.scope_id,
        "enabled": definition.enabled,
        **data,
    }
    _validate_definition_payload(db, merged)
    for field, value in data.items():
        setattr(definition, field, value)
    definition.update_time = datetime.now()
    db.commit()
    db.refresh(definition)
    return definition


def disable_definition(db: Session, definition_id: int) -> None:
    definition = _get_definition(db, definition_id)
    definition.enabled = False
    definition.update_time = datetime.now()
    db.commit()


def get_graph(db: Session, definition_id: int) -> dict:
    definition = _get_definition(db, definition_id)
    return _graph_response(db, definition)


def save_graph(db: Session, definition_id: int, payload: WorkflowGraphSave) -> dict:
    definition = _get_definition(db, definition_id)
    _validate_graph(definition.object_type, payload)
    _replace_graph(db, definition, payload)
    _sync_handler_rules(db, definition, payload.transitions)
    definition.version = (definition.version or 1) + 1
    definition.update_time = datetime.now()
    db.commit()
    db.refresh(definition)
    return _graph_response(db, definition)


def apply_template(db: Session, definition_id: int) -> dict:
    definition = _get_definition(db, definition_id)
    template = _template_for(definition.object_type)
    return save_graph(db, definition_id, template)


def _get_definition(db: Session, definition_id: int) -> WorkflowDefinition:
    definition = db.query(WorkflowDefinition).filter(WorkflowDefinition.id == definition_id).first()
    if not definition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow definition not found")
    return definition


def _validate_definition_payload(db: Session, data: dict) -> None:
    if data["object_type"] not in OBJECT_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown workflow object type")
    if data["scope_type"] not in SCOPE_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown workflow scope type")
    if data["scope_type"] == "assignee_rule_config":
        if not data.get("scope_id"):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Scope id is required")
        exists = db.query(AssigneeRuleConfig.id).filter(AssigneeRuleConfig.id == data["scope_id"]).first()
        if not exists:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assignee rule config not found")


def _validate_graph(object_type: str, payload: WorkflowGraphSave) -> None:
    status_keys: set[str] = set()
    for state in payload.states:
        if state.category not in STATE_CATEGORIES:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown state category")
        if state.status_key in status_keys:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Duplicate status key")
        status_keys.add(state.status_key)
    transition_keys: set[tuple[str, str, str]] = set()
    for transition in payload.transitions:
        if transition.from_status not in status_keys or transition.to_status not in status_keys:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Transition references unknown state")
        key = (transition.action_key, transition.from_status, transition.to_status)
        if key in transition_keys:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Duplicate transition")
        transition_keys.add(key)
        _validate_handler_rule(transition.handler_rule)


def _validate_handler_rule(handler_rule: dict | None) -> None:
    if not handler_rule:
        return
    target_type = handler_rule.get("target_type", "keep_current")
    fallback_type = handler_rule.get("fallback_type", "keep_current")
    if target_type == "project_role" and not handler_rule.get("target_roles"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Target roles are required")
    if fallback_type == "project_role" and not handler_rule.get("fallback_roles"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Fallback roles are required")


def _replace_graph(db: Session, definition: WorkflowDefinition, payload: WorkflowGraphSave) -> None:
    db.query(WorkflowTransition).filter(WorkflowTransition.definition_id == definition.id).delete(synchronize_session=False)
    db.query(WorkflowState).filter(WorkflowState.definition_id == definition.id).delete(synchronize_session=False)
    for state in payload.states:
        db.add(WorkflowState(definition_id=definition.id, **state.model_dump()))
    for transition in payload.transitions:
        db.add(WorkflowTransition(definition_id=definition.id, **transition.model_dump()))


def _sync_handler_rules(db: Session, definition: WorkflowDefinition, transitions: list[WorkflowTransitionBase]) -> None:
    if definition.scope_type != "assignee_rule_config" or not definition.scope_id:
        return
    for transition in transitions:
        handler_rule = transition.handler_rule or {}
        if not handler_rule:
            continue
        rule = (
            db.query(HandlerTransitionRule)
            .filter(
                HandlerTransitionRule.config_id == definition.scope_id,
                HandlerTransitionRule.rule_type == "advanced",
                HandlerTransitionRule.object_type == definition.object_type,
                HandlerTransitionRule.action == transition.action_key,
                HandlerTransitionRule.from_status == transition.from_status,
                HandlerTransitionRule.to_status == transition.to_status,
            )
            .first()
        )
        data = {
            "config_id": definition.scope_id,
            "rule_type": "advanced",
            "object_type": definition.object_type,
            "action": transition.action_key,
            "from_status": transition.from_status,
            "to_status": transition.to_status,
            "target_type": handler_rule.get("target_type", "keep_current"),
            "target_roles": _csv(handler_rule.get("target_roles")),
            "fallback_type": handler_rule.get("fallback_type", "keep_current"),
            "fallback_roles": _csv(handler_rule.get("fallback_roles")),
            "enabled": transition.enabled,
        }
        if rule:
            for field, value in data.items():
                setattr(rule, field, value)
            rule.update_time = datetime.now()
        else:
            db.add(HandlerTransitionRule(**data))


def _graph_response(db: Session, definition: WorkflowDefinition) -> dict:
    states = (
        db.query(WorkflowState)
        .filter(WorkflowState.definition_id == definition.id)
        .order_by(WorkflowState.sort_order.asc(), WorkflowState.id.asc())
        .all()
    )
    transitions = (
        db.query(WorkflowTransition)
        .filter(WorkflowTransition.definition_id == definition.id)
        .order_by(WorkflowTransition.sort_order.asc(), WorkflowTransition.id.asc())
        .all()
    )
    return {"definition": definition, "states": states, "transitions": transitions}


def _template_for(object_type: str) -> WorkflowGraphSave:
    if object_type == "requirement":
        return WorkflowGraphSave(
            states=[
                _state("draft", "草稿", "start", "#475569", 120, 80),
                _state("active", "激活", "normal", "#2563eb", 320, 80),
                _state("pending_validation", "待验证", "normal", "#0f766e", 520, 80),
                _state("validation_failed", "验证未通过", "normal", "#d97706", 520, 230),
                _state("done", "完成", "terminal", "#059669", 720, 80),
                _state("closed", "关闭", "terminal", "#64748b", 320, 230),
            ],
            transitions=[
                _transition("activate", "激活", "draft", "active", target_roles="development_lead,developer"),
                _transition("submit_validation", "提交验证", "active", "pending_validation", target_roles="test_lead,tester"),
                _transition("validation_failed", "验证失败", "pending_validation", "validation_failed", target_roles="development_lead,developer"),
                _transition("activate", "重新激活", "validation_failed", "active", target_roles="development_lead,developer"),
                _transition("complete", "验证通过", "pending_validation", "done", target_type="keep_current"),
                _transition("close", "关闭", "active", "closed", target_type="keep_current"),
            ],
        )
    if object_type == "task":
        return WorkflowGraphSave(
            states=[
                _state("todo", "待办", "start", "#475569", 120, 120),
                _state("doing", "进行中", "normal", "#2563eb", 340, 120),
                _state("done", "完成", "terminal", "#059669", 560, 120),
                _state("closed", "关闭", "terminal", "#64748b", 340, 260),
            ],
            transitions=[
                _transition("activate", "激活", "todo", "doing", target_roles="development_lead,developer"),
                _transition("complete", "完成", "doing", "done", target_type="keep_current"),
                _transition("close", "关闭", "todo", "closed", target_type="keep_current"),
                _transition("close", "关闭", "doing", "closed", target_type="keep_current"),
            ],
        )
    return WorkflowGraphSave(
        states=[
            _state("open", "待确认", "start", "#475569", 120, 80),
            _state("fixing", "修复中", "normal", "#2563eb", 320, 80),
            _state("verifying", "待验证", "normal", "#0f766e", 520, 80),
            _state("reopened", "重新打开", "normal", "#d97706", 520, 240),
            _state("suspended", "已挂起", "normal", "#7c3aed", 320, 240),
            _state("closed", "已关闭", "terminal", "#059669", 720, 80),
        ],
        transitions=[
            _transition("start_fixing", "开始修复", "open", "fixing", target_roles="development_lead,developer"),
            _transition("resolve", "解决", "fixing", "verifying", target_roles="test_lead,tester"),
            _transition("verify_passed", "验证通过", "verifying", "closed", target_type="keep_current"),
            _transition(
                "verify_failed",
                "验证失败",
                "verifying",
                "reopened",
                target_type="last_resolver",
                fallback_type="project_role",
                fallback_roles="development_lead,developer",
            ),
            _transition("start_fixing", "重新修复", "reopened", "fixing", target_roles="development_lead,developer"),
            _transition("suspend", "挂起", "fixing", "suspended", target_type="keep_current"),
            _transition("activate", "激活", "suspended", "open", target_roles="development_lead,developer"),
        ],
    )


def _state(status_key: str, status_name: str, category: str, color: str, x: int, y: int) -> WorkflowStateBase:
    return WorkflowStateBase(status_key=status_key, status_name=status_name, category=category, color=color, x=x, y=y)


def _transition(
    action_key: str,
    action_name: str,
    from_status: str,
    to_status: str,
    *,
    target_type: str = "project_role",
    target_roles: str = "",
    fallback_type: str = "keep_current",
    fallback_roles: str = "",
) -> WorkflowTransitionBase:
    return WorkflowTransitionBase(
        action_key=action_key,
        action_name=action_name,
        from_status=from_status,
        to_status=to_status,
        handler_rule={
            "target_type": target_type,
            "target_roles": target_roles,
            "fallback_type": fallback_type,
            "fallback_roles": fallback_roles,
        },
    )


def _csv(value) -> str:
    if isinstance(value, list):
        return ",".join(str(item).strip() for item in value if str(item).strip())
    return ",".join(str(item).strip() for item in str(value or "").split(",") if str(item).strip())
