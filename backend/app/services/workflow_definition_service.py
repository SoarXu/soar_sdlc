from copy import deepcopy
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.assignee_rule_config import AssigneeRuleConfig
from app.models.bug import Bug
from app.models.requirement import Requirement
from app.models.role import Role
from app.models.status_operation import StatusOperationLog
from app.models.task import Task
from app.models.workflow_definition import WorkflowDefinition, WorkflowState, WorkflowTransition
from app.services.default_workflow_template_service import ensure_default_workflow_templates, graph_for_object_type
from app.views.workflow_definition_view import (
    WorkflowDefinitionCreate,
    WorkflowDefinitionUpdate,
    WorkflowGraphSave,
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
    "target_state_id_by_owner", "target_status_by_owner",
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
    _save_graph(db, definition, payload)
    return _graph_response(db, definition)


def _save_graph(
    db: Session,
    definition: WorkflowDefinition,
    payload: WorkflowGraphSave,
) -> None:
    _validate_graph(db, definition, payload)
    _persist_graph(db, definition, payload)
    definition.version = (definition.version or 1) + 1
    definition.update_time = datetime.now()
    db.commit()
    db.refresh(definition)


def apply_template(db: Session, definition_id: int) -> dict:
    definition = _get_definition(db, definition_id)
    payload = _template_graph_payload(
        db,
        definition,
        graph_for_object_type(definition.object_type),
    )
    _save_graph(db, definition, payload)
    return _graph_response(db, definition)


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


def _validate_graph(db: Session, definition: WorkflowDefinition, payload: WorkflowGraphSave) -> None:
    if definition.object_type not in OBJECT_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown workflow object type")
    state_ids: set[int] = set()
    for state in payload.states:
        if state.category not in STATE_CATEGORIES:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown state category")
        if state.id in state_ids:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Duplicate state id")
        state_ids.add(state.id)
    if payload.states and payload.initial_state_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Initial state is required")
    if payload.initial_state_id is not None and payload.initial_state_id not in state_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Initial state is not in this graph")
    initial = next((item for item in payload.states if item.id == payload.initial_state_id), None)
    if initial and not initial.enabled:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Initial state must be enabled")
    transition_ids: set[int] = set()
    transition_keys: set[tuple[str, int, int]] = set()
    for transition in payload.transitions:
        if transition.id is not None and transition.id > 0:
            if transition.id in transition_ids:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Duplicate transition id")
            transition_ids.add(transition.id)
        if transition.from_state_id not in state_ids or transition.to_state_id not in state_ids:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Transition references unknown state")
        key = (transition.action_key, transition.from_state_id, transition.to_state_id)
        if key in transition_keys:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Duplicate transition")
        transition_keys.add(key)
        _validate_roles(db, transition.allowed_roles)
        _validate_handler_rule(db, transition.handler_rule)
        _validate_condition_config(db, transition.condition_config, state_ids)
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


def _validate_condition_config(db: Session, config: dict | list | None, state_ids: set[int]) -> None:
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
        if set(routes.values()) - state_ids:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Condition route references unknown state")
    owner_targets = config.get("target_state_id_by_owner") or config.get("target_status_by_owner") or {}
    if not isinstance(owner_targets, dict) or set(owner_targets.values()) - state_ids:
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


def _persist_graph(
    db: Session,
    definition: WorkflowDefinition,
    payload: WorkflowGraphSave,
) -> list[WorkflowTransition]:
    existing_states = {
        item.id: item
        for item in db.query(WorkflowState).filter(WorkflowState.definition_id == definition.id).all()
    }
    submitted_positive_state_ids = {item.id for item in payload.states if item.id > 0}
    unknown_state_ids = submitted_positive_state_ids - set(existing_states)
    if unknown_state_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"State does not belong to this definition: {min(unknown_state_ids)}",
        )

    state_id_map: dict[int, int] = {}
    persisted_states: dict[int, WorkflowState] = {}
    for item in payload.states:
        data = item.model_dump(exclude={"id"})
        if item.id > 0:
            state = existing_states[item.id]
            for field, value in data.items():
                setattr(state, field, value)
        else:
            state = WorkflowState(
                definition_id=definition.id,
                **data,
            )
            db.add(state)
            db.flush()
        state_id_map[item.id] = state.id
        persisted_states[state.id] = state
    db.flush()

    initial_state_id = (
        state_id_map[payload.initial_state_id]
        if payload.initial_state_id is not None
        else None
    )
    if initial_state_id is not None and not persisted_states[initial_state_id].enabled:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Initial state must be enabled")

    existing_transitions = {
        item.id: item
        for item in db.query(WorkflowTransition).filter(WorkflowTransition.definition_id == definition.id).all()
    }
    submitted_transition_ids: set[int] = set()
    persisted_transitions: list[WorkflowTransition] = []
    for item in payload.transitions:
        from_state_id = state_id_map[item.from_state_id]
        to_state_id = state_id_map[item.to_state_id]
        data = item.model_dump(exclude={"id", "from_state_id", "to_state_id"})
        data["condition_config"] = _remap_condition_state_ids(data.get("condition_config"), state_id_map)
        if item.id is not None and item.id > 0:
            transition = existing_transitions.get(item.id)
            if not transition:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Transition does not belong to this definition: {item.id}",
                )
            submitted_transition_ids.add(item.id)
            for field, value in data.items():
                setattr(transition, field, value)
        else:
            transition = WorkflowTransition(definition_id=definition.id, **data)
            db.add(transition)
        transition.from_state_id = from_state_id
        transition.to_state_id = to_state_id
        persisted_transitions.append(transition)
    db.flush()

    omitted_transition_ids = set(existing_transitions) - submitted_transition_ids
    if omitted_transition_ids:
        db.query(WorkflowTransition).filter(WorkflowTransition.id.in_(omitted_transition_ids)).delete(
            synchronize_session=False
        )

    definition.initial_state_id = initial_state_id
    db.flush()
    for state_id in set(existing_states) - submitted_positive_state_ids:
        state = existing_states[state_id]
        if _state_is_referenced(db, state_id):
            state.enabled = False
        else:
            db.delete(state)
    db.flush()
    return persisted_transitions


def _state_is_referenced(db: Session, state_id: int) -> bool:
    reference_queries = (
        db.query(Requirement.id).filter(Requirement.current_state_id == state_id),
        db.query(Task.id).filter(Task.current_state_id == state_id),
        db.query(Bug.id).filter(Bug.current_state_id == state_id),
        db.query(StatusOperationLog.id).filter(
            (StatusOperationLog.from_state_id == state_id) | (StatusOperationLog.to_state_id == state_id)
        ),
        db.query(WorkflowDefinition.id).filter(WorkflowDefinition.initial_state_id == state_id),
        db.query(WorkflowTransition.id).filter(
            (WorkflowTransition.from_state_id == state_id) | (WorkflowTransition.to_state_id == state_id)
        ),
    )
    return any(query.first() is not None for query in reference_queries)


def _remap_condition_state_ids(config: dict | list | None, state_id_map: dict[int, int]):
    if not config or not isinstance(config, dict):
        return config
    remapped = deepcopy(config)
    if isinstance(remapped.get("routes"), dict):
        remapped["routes"] = {
            key: state_id_map.get(value, value)
            for key, value in remapped["routes"].items()
        }
    owner_targets = remapped.pop("target_status_by_owner", None)
    if owner_targets is not None:
        remapped["target_state_id_by_owner"] = owner_targets
    if isinstance(remapped.get("target_state_id_by_owner"), dict):
        remapped["target_state_id_by_owner"] = {
            key: state_id_map.get(value, value)
            for key, value in remapped["target_state_id_by_owner"].items()
        }
    return remapped


def _template_graph_payload(db: Session, definition: WorkflowDefinition, template) -> WorkflowGraphSave:
    ref_to_input_id: dict[str, int] = {}
    states = []
    next_temp_id = -1
    for item in template.states:
        input_id = next_temp_id
        next_temp_id -= 1
        ref_to_input_id[item.ref] = input_id
        states.append({"id": input_id, **item.model_dump(exclude={"ref"})})

    transitions = []
    for item in template.transitions:
        data = item.model_dump(exclude={"from_ref", "to_ref"})
        data["id"] = None
        data["from_state_id"] = ref_to_input_id[item.from_ref]
        data["to_state_id"] = ref_to_input_id[item.to_ref]
        condition = deepcopy(data.get("condition_config"))
        if isinstance(condition, dict):
            if isinstance(condition.get("routes"), dict):
                condition["routes"] = {
                    key: ref_to_input_id[value]
                    for key, value in condition["routes"].items()
                }
            owner_targets = condition.pop("target_status_by_owner", None)
            if owner_targets is not None:
                condition["target_state_id_by_owner"] = {
                    key: ref_to_input_id[value]
                    for key, value in owner_targets.items()
                }
        data["condition_config"] = condition
        transitions.append(data)
    initial = next((item for item in template.states if item.category == "start"), None)
    return WorkflowGraphSave(
        initial_state_id=ref_to_input_id[initial.ref] if initial else None,
        states=states,
        transitions=transitions,
    )


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
