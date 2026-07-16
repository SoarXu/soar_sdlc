from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.assignee_rule_config import AssigneeRuleConfig
from app.models.handler_transition_rule import HandlerTransitionRule
from app.models.role import Role
from app.models.workflow_definition import WorkflowDefinition, WorkflowState, WorkflowTransition
from app.services.default_workflow_template_service import ensure_default_workflow_templates, graph_for_object_type
from app.views.workflow_definition_view import (
    WorkflowDefinitionCreate,
    WorkflowDefinitionUpdate,
    WorkflowGraphSave,
    WorkflowTransitionBase,
)


OBJECT_TYPES = {"requirement", "task", "bug", "iteration", "project"}
SCOPE_TYPES = {"system", "project", "assignee_rule_config"}
STATE_CATEGORIES = {"start", "normal", "terminal"}
IDENTITY_ROLES = {
    "system_admin", "project_owner", "project_member", "current_handler", "owner",
    "creator", "reporter", "proposer", "tester",
}
HANDLER_SOURCE_TYPES = {
    "keep_current", "none", "actor", "explicit_owner", "creator", "proposer",
    "reporter", "bug_reporter", "last_resolver", "previous_handler", "project_role",
    "fixed_role", "project_owner", "fixed_user", "requirement_owner", "source_owner",
    "test_executor", "test_case_default_tester", "bug_verifier",
    "bug_verifier_if_pending_verification", "task_confirmation",
}
VALIDATOR_TYPES = {
    "bug_close_gate", "requirement_terminal_gate", "iteration_terminal_gate", "project_close_gate",
}
FORM_FIELD_TYPES = {"text", "textarea", "select", "number", "date", "datetime"}
UI_CONFIG_KEYS = {
    "button_type", "list_display", "list_priority", "confirm_required", "hidden",
    "ownerless_only", "requires_owner", "handler_scope", "command_type",
    "action_category", "visible_in_detail", "visible_in_list",
}
CONDITION_CONFIG_KEYS = {
    "task_types", "field", "routes", "route_dictionary", "routing_mode", "allow_override_roles",
    "target_status_by_owner",
}
FORM_CONFIG_KEYS = {"title", "submit_text", "fields", "allow_manual_owner"}
FORM_FIELD_KEYS = {
    "field", "label", "type", "required", "options", "dictionary", "placeholder", "min", "max",
}
ROUTING_MODES = {"automatic", "manual_allowed", "automatic_with_override"}
AUTOMATION_TYPES = {"notification"}
NOTIFICATION_RECEIVERS = {"actor", "current_handler", "next_handler", "creator", "project_owner"}


def list_definitions(
    db: Session,
    object_type: str | None = None,
    scope_type: str | None = None,
    scope_id: int | None = None,
) -> list[WorkflowDefinition]:
    ensure_default_workflow_templates(db)
    query = db.query(WorkflowDefinition)
    if object_type:
        query = query.filter(WorkflowDefinition.object_type == object_type)
    if scope_type:
        query = query.filter(WorkflowDefinition.scope_type == scope_type)
    if scope_id is not None:
        query = query.filter(WorkflowDefinition.scope_id == scope_id)
    return query.order_by(
        WorkflowDefinition.is_default_template.desc(),
        WorkflowDefinition.object_type.asc(),
        WorkflowDefinition.id.desc(),
    ).all()


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
        "template_key": definition.template_key,
        "parent_definition_id": definition.parent_definition_id,
        "is_default_template": definition.is_default_template,
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
    ensure_default_workflow_templates(db)
    definition = _get_definition(db, definition_id)
    return _graph_response(db, definition)


def save_graph(db: Session, definition_id: int, payload: WorkflowGraphSave) -> dict:
    definition = _get_definition(db, definition_id)
    _validate_graph(db, definition.object_type, payload)
    _replace_graph(db, definition, payload)
    _sync_handler_rules(db, definition, payload.transitions)
    definition.version = (definition.version or 1) + 1
    definition.update_time = datetime.now()
    db.commit()
    db.refresh(definition)
    return _graph_response(db, definition)


def apply_template(db: Session, definition_id: int) -> dict:
    definition = _get_definition(db, definition_id)
    return save_graph(db, definition_id, graph_for_object_type(definition.object_type))


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


def _validate_graph(db: Session, object_type: str, payload: WorkflowGraphSave) -> None:
    if object_type not in OBJECT_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown workflow object type")
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
        _validate_roles(db, transition.allowed_roles)
        _validate_handler_rule(db, transition.handler_rule)
        _validate_condition_config(db, transition.condition_config, status_keys)
        _validate_form_config(transition.form_config)
        _validate_typed_config(transition.validator_config, VALIDATOR_TYPES, "validator")
        _validate_ui_config(transition.ui_config)
        _validate_automation_config(transition.trigger_config, "trigger")
        _validate_automation_config(transition.post_action_config, "post action")


def _validate_handler_rule(db: Session, handler_rule: dict | None) -> None:
    if not handler_rule:
        return
    target_type = handler_rule.get("target_type", "keep_current")
    fallback_type = handler_rule.get("fallback_type", "keep_current")
    if target_type not in HANDLER_SOURCE_TYPES or fallback_type not in HANDLER_SOURCE_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown handler source type")
    if target_type == "project_role" and not handler_rule.get("target_roles"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Target roles are required")
    if fallback_type == "project_role" and not handler_rule.get("fallback_roles"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Fallback roles are required")
    _validate_roles(db, handler_rule.get("target_roles"))
    _validate_roles(db, handler_rule.get("fallback_roles"))


def _validate_roles(db: Session, value) -> None:
    role_keys = set(_csv(value).split(",")) - {""}
    if not role_keys:
        return
    persisted = {
        item[0]
        for item in db.query(Role.role_key).filter(Role.role_key.in_(role_keys), Role.enabled.is_(True)).all()
    }
    unknown = role_keys - persisted - IDENTITY_ROLES
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown workflow role(s): {', '.join(sorted(unknown))}",
        )


def _validate_condition_config(db: Session, config: dict | list | None, status_keys: set[str]) -> None:
    if not config:
        return
    if not isinstance(config, dict) or set(config) - CONDITION_CONFIG_KEYS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported condition configuration")
    routes = config.get("routes")
    route_dictionary = config.get("route_dictionary")
    if route_dictionary and route_dictionary != "bug_type":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown route dictionary")
    if route_dictionary and (not config.get("field") or routes):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Dictionary routing requires a field and no static routes")
    if "routes" in config:
        if not isinstance(routes, dict) or not routes or not config.get("field"):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Condition routes and field are required")
        if set(routes.values()) - status_keys:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Condition route references unknown state")
    owner_targets = config.get("target_status_by_owner") or {}
    if not isinstance(owner_targets, dict) or set(owner_targets.values()) - status_keys:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Owner route references unknown state")
    if config.get("routing_mode") and config["routing_mode"] not in ROUTING_MODES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown routing mode")
    _validate_roles(db, config.get("allow_override_roles"))


def _validate_form_config(config: dict | None) -> None:
    if not config:
        return
    if not isinstance(config, dict) or set(config) - FORM_CONFIG_KEYS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported form configuration")
    fields = config.get("fields") or []
    if not isinstance(fields, list):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Form fields must be a list")
    for field in fields:
        if not isinstance(field, dict) or set(field) - FORM_FIELD_KEYS:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported form field configuration")
        if not field.get("field") or not field.get("label") or field.get("type") not in FORM_FIELD_TYPES:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid form field")
        if field.get("type") == "select":
            options = field.get("options")
            is_bug_type_dictionary = field.get("dictionary") == "bug_type" or field.get("field") == "bug_type"
            if not is_bug_type_dictionary and (not isinstance(options, list) or not options):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Select field options are required")
            for option in options or []:
                if not isinstance(option, dict) or "label" not in option or "value" not in option:
                    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid select option")


def _validate_typed_config(config: dict | list | None, allowed_types: set[str], label: str) -> None:
    if not config:
        return
    entries = config if isinstance(config, list) else [config]
    if any(not isinstance(item, dict) or item.get("type") not in allowed_types for item in entries):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unsupported {label} type")


def _validate_ui_config(config: dict | None) -> None:
    if config and (not isinstance(config, dict) or set(config) - UI_CONFIG_KEYS):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported UI configuration")


def _validate_automation_config(config: dict | list | None, label: str) -> None:
    if not config:
        return
    entries = config if isinstance(config, list) else [config]
    for item in entries:
        if not isinstance(item, dict) or item.get("type") not in AUTOMATION_TYPES:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unsupported {label} type")
        if item.get("receiver") not in NOTIFICATION_RECEIVERS or not str(item.get("title") or "").strip():
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid {label} notification")


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


def _csv(value) -> str:
    if isinstance(value, list):
        return ",".join(str(item).strip() for item in value if str(item).strip())
    return ",".join(str(item).strip() for item in str(value or "").split(",") if str(item).strip())
