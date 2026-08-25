from collections import defaultdict
from copy import deepcopy
from datetime import datetime
from math import isfinite
from uuid import uuid4
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.assignee_rule_config import AssigneeRuleConfig
from app.models.bug import Bug
from app.models.requirement import Requirement
from app.models.role import Role
from app.models.role import RoleCapability
from app.models.status_operation import StatusOperationLog
from app.models.task import Task
from app.models.workflow_definition import WorkflowDefinition, WorkflowState, WorkflowTransition, WorkflowTransitionRole
from app.services.default_workflow_template_service import ensure_default_workflow_templates, graph_for_object_type
from app.views.workflow_definition_view import (
    WorkflowDefinitionCreate,
    WorkflowDefinitionRead,
    WorkflowDefinitionUpdate,
    WorkflowGraphSave,
    WorkflowTemplateGraphSave,
    WorkflowTransitionSave,
)


OBJECT_TYPES = {"requirement", "task", "bug", "iteration", "project"}
WORK_ITEM_STATE_ROLE_OBJECT_TYPES = {"requirement", "task", "bug"}
WORK_ITEM_STATE_ROLES = {"unassigned", "waiting_iteration", "active_work"}
SCOPE_TYPES = {"system", "project", "assignee_rule_config"}
STATE_CATEGORIES = {"start", "normal", "terminal"}
TERMINAL_KINDS = {"completed", "terminated"}
IDENTITY_ROLES = {
    "system_admin", "project_member", "current_handler", "owner", "creator", "reporter", "proposer",
}
TEMPLATE_CAPABILITY_ALIASES = {
    "product_owner": ("product_owner", "product_manager"),
    "tech_lead": ("tech_lead", "development_lead"),
    "test_lead": ("test_lead", "tester"),
}
HANDLER_SOURCE_TYPES = {
    "keep_current", "none", "actor", "explicit_owner", "creator", "proposer",
    "reporter", "bug_reporter", "last_resolver", "previous_handler", "project_role",
    "fixed_role", "project_owner", "fixed_user", "requirement_owner", "source_owner",
    "test_executor", "test_case_default_tester", "bug_verifier",
    "bug_verifier_if_pending_verification", "task_confirmation",
}
VALIDATOR_TYPES = {
    "bug_close_gate", "requirement_terminal_gate", "task_descendants_terminal_gate", "iteration_terminal_gate", "project_close_gate",
}
FORM_FIELD_TYPES = {"text", "textarea", "select", "number", "date", "datetime"}
UI_CONFIG_KEYS = {
    "button_type", "list_display", "confirm_required",
    "ownerless_only", "requires_owner", "handler_scope", "command_type",
    "action_category", "system_action",
}
CONDITION_CONFIG_KEYS = {
    "task_types", "field", "routes", "route_dictionary", "routing_mode", "allow_override_role_ids",
    "target_state_id_by_owner", "target_status_by_owner", "target_state_role_by_iteration_phase",
}
FORM_CONFIG_KEYS = {"title", "submit_text", "fields", "allow_manual_owner", "allow_unassigned"}
FORM_FIELD_KEYS = {
    "field", "label", "type", "required", "options", "dictionary", "placeholder", "min", "max",
}
ROUTING_MODES = {"automatic", "manual_allowed", "automatic_with_override"}
AUTOMATION_TYPES = {"notification", "system_action"}
NOTIFICATION_RECEIVERS = {"actor", "current_handler", "next_handler", "creator", "project_owner"}
DIAGRAM_SIDES = {"top", "right", "bottom", "left"}
MAX_DIAGRAM_WAYPOINTS = 32
DIAGRAM_NODE_WIDTH = 118
DIAGRAM_NODE_HEIGHT = 42
DIAGRAM_CORNER_GUARD = 8


def list_definitions(
    db: Session,
    object_type: str | None = None,
    scope_type: str | None = None,
    scope_id: int | None = None,
) -> list[WorkflowDefinition]:
    ensure_default_workflow_templates(db, reconcile_existing=False)
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
    _validate_definition_payload(db, merged, excluding_definition_id=definition.id)
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
    ensure_default_workflow_templates(db, reconcile_existing=False)
    definition = _get_definition(db, definition_id)
    return _graph_response(db, definition)


def save_graph(db: Session, definition_id: int, payload: WorkflowGraphSave) -> dict:
    definition = _get_definition(db, definition_id)
    payload = _normalize_legacy_template_references(db, definition, payload)
    payload = _synchronize_transition_state_availability(db, definition, payload)
    _save_graph(
        db,
        definition,
        payload,
        disable_omitted_transitions=payload.replace_existing_transitions,
    )
    if definition.scope_type != "system":
        definition.parent_definition_id = None
    return _graph_response(db, definition)


def _normalize_legacy_template_references(
    db: Session,
    definition: WorkflowDefinition,
    payload: WorkflowGraphSave,
) -> WorkflowGraphSave:
    template = graph_for_object_type(definition.object_type)
    normalized = payload.model_copy(deep=True)
    for transition in normalized.transitions:
        _normalize_legacy_transition_role_references(db, transition)
    submitted_by_identity: dict[tuple[str, str], list[int]] = defaultdict(list)
    for state in normalized.states:
        submitted_by_identity[(state.status_name, state.category)].append(state.id)

    ref_to_state_id = {}
    for template_state in template.states:
        matches = submitted_by_identity[(template_state.status_name, template_state.category)]
        if len(matches) == 1:
            ref_to_state_id[template_state.ref] = matches[0]

    if not ref_to_state_id:
        return normalized

    existing_action_keys = {
        item.id: item.action_key
        for item in db.query(WorkflowTransition).filter(
            WorkflowTransition.definition_id == definition.id
        ).all()
    }
    templates_by_action_key: dict[str, list] = defaultdict(list)
    for template_transition in template.transitions:
        templates_by_action_key[template_transition.action_key].append(template_transition)

    state_ids = {state.id for state in normalized.states}
    for transition in normalized.transitions:
        action_key = transition.action_key or existing_action_keys.get(transition.id)
        candidates = templates_by_action_key.get(action_key, [])
        template_transition = next((
            item for item in candidates
            if ref_to_state_id.get(item.from_ref) == transition.from_state_id
            and ref_to_state_id.get(item.to_ref) == transition.to_state_id
        ), None)
        if not template_transition:
            continue
        expected = template_transition.condition_config
        if isinstance(transition.condition_config, dict) and isinstance(expected, dict):
            transition.condition_config = _normalize_template_condition_references(
                transition.condition_config,
                expected,
                ref_to_state_id,
                state_ids,
            )
        if _is_legacy_template_form_config(transition.form_config, template_transition.form_config):
            transition.form_config = _normalize_legacy_template_form_config(
                transition.form_config,
                template_transition.form_config,
            )
    return normalized


def _normalize_template_condition_references(
    condition_config: dict,
    expected: dict,
    ref_to_state_id: dict[str, int],
    state_ids: set[int],
) -> dict:
    normalized = deepcopy(condition_config)
    routes = normalized.get("routes")
    if isinstance(routes, dict) and set(routes.values()) - state_ids:
        mapped_routes = _map_legacy_state_values(routes, ref_to_state_id, state_ids)
        if expected.get("route_dictionary") and mapped_routes is not None and all(
            isinstance(value, str) for value in routes.values()
        ):
            normalized.pop("routes", None)
            for key in ("field", "routing_mode", "route_dictionary"):
                if key in expected:
                    normalized[key] = deepcopy(expected[key])
        elif isinstance(expected.get("routes"), dict) and mapped_routes is not None:
            normalized["routes"] = mapped_routes

    owner_targets = (
        normalized.get("target_state_id_by_owner")
        or normalized.get("target_status_by_owner")
    )
    if isinstance(owner_targets, dict) and set(owner_targets.values()) - state_ids:
        expected_targets = (
            expected.get("target_status_by_owner")
            or expected.get("target_state_id_by_owner")
        )
        if isinstance(expected_targets, dict):
            mapped_targets = _map_legacy_state_values(owner_targets, ref_to_state_id, state_ids)
            if (
                mapped_targets is None
                and set(owner_targets) == set(expected_targets)
                and all(value not in state_ids for value in owner_targets.values())
            ):
                mapped_targets = _map_template_state_refs(expected_targets, ref_to_state_id)
            if mapped_targets is not None:
                normalized.pop("target_status_by_owner", None)
                normalized["target_state_id_by_owner"] = mapped_targets
    return normalized


def _map_template_state_refs(values: dict, ref_to_state_id: dict[str, int]) -> dict | None:
    if set(values.values()) - set(ref_to_state_id):
        return None
    return {key: ref_to_state_id[value] for key, value in values.items()}


def _map_legacy_state_values(
    values: dict,
    ref_to_state_id: dict[str, int],
    state_ids: set[int],
) -> dict | None:
    mapped = {}
    for key, value in values.items():
        if value in state_ids:
            mapped[key] = value
        elif isinstance(value, str) and value in ref_to_state_id:
            mapped[key] = ref_to_state_id[value]
        else:
            return None
    return mapped


def _is_legacy_template_form_config(current: dict | None, expected: dict | None) -> bool:
    if not isinstance(current, dict) or not isinstance(expected, dict):
        return False
    current_fields = current.get("fields")
    expected_fields = expected.get("fields")
    if not isinstance(current_fields, list) or not current_fields or not isinstance(expected_fields, list):
        return False
    expected_by_name = {
        field.get("field"): field
        for field in expected_fields
        if isinstance(field, dict) and field.get("field")
    }
    return all(
        isinstance(field, dict)
        and not field.get("label")
        and field.get("field") in expected_by_name
        and field.get("type") == expected_by_name[field["field"]].get("type")
        for field in current_fields
    )


def _normalize_legacy_template_form_config(current: dict, expected: dict) -> dict:
    normalized = deepcopy(current)
    expected_by_name = {
        field.get("field"): field
        for field in expected["fields"]
        if isinstance(field, dict) and field.get("field")
    }
    for field in normalized["fields"]:
        expected_field = expected_by_name[field["field"]]
        for key in ("label", "dictionary", "options"):
            if key not in field and key in expected_field:
                field[key] = deepcopy(expected_field[key])
    return normalized


def _normalize_legacy_transition_role_references(
    db: Session,
    transition: WorkflowTransitionSave,
) -> None:
    identities, role_ids = _template_role_values(db, transition.allowed_roles)
    transition.allowed_roles = ",".join(identities)
    if role_ids:
        transition.allowed_role_ids = list(dict.fromkeys([*transition.allowed_role_ids, *role_ids]))

    handler_rule = dict(transition.handler_rule or {})
    for legacy_field, role_field in (
        ("target_roles", "handler_target_role_ids"),
        ("fallback_roles", "handler_fallback_role_ids"),
    ):
        if legacy_field not in handler_rule:
            continue
        _identities, role_ids = _template_role_values(db, handler_rule.pop(legacy_field))
        if role_ids:
            current_ids = getattr(transition, role_field)
            setattr(transition, role_field, list(dict.fromkeys([*current_ids, *role_ids])))
    transition.handler_rule = handler_rule or None

    if not isinstance(transition.condition_config, dict):
        return
    condition = dict(transition.condition_config)
    if "allow_override_roles" not in condition:
        return
    _identities, role_ids = _template_role_values(db, condition.pop("allow_override_roles"))
    if role_ids:
        current_ids = condition.get("allow_override_role_ids") or []
        condition["allow_override_role_ids"] = list(dict.fromkeys([*current_ids, *role_ids]))
    transition.condition_config = condition


def _synchronize_transition_state_availability(
    db: Session,
    definition: WorkflowDefinition,
    payload: WorkflowGraphSave,
) -> WorkflowGraphSave:
    state_enabled = {state.id: state.enabled for state in payload.states}
    existing_markers = {
        transition.id: bool(transition.auto_disabled_by_state)
        for transition in db.query(WorkflowTransition).filter(
            WorkflowTransition.definition_id == definition.id
        ).all()
    }
    synchronized = payload.model_copy(deep=True)
    for transition in synchronized.transitions:
        marker = (
            transition.auto_disabled_by_state
            if "auto_disabled_by_state" in transition.model_fields_set
            else existing_markers.get(transition.id, False)
        )
        from_enabled = state_enabled.get(transition.from_state_id)
        to_enabled = state_enabled.get(transition.to_state_id)
        if from_enabled is None or to_enabled is None:
            continue
        if not from_enabled or not to_enabled:
            if transition.enabled:
                marker = True
            transition.enabled = False
        elif marker:
            transition.enabled = True
            marker = False
        transition.auto_disabled_by_state = marker
    return synchronized


def _save_graph(
    db: Session,
    definition: WorkflowDefinition,
    payload: WorkflowGraphSave,
    *,
    disable_omitted_transitions: bool = False,
) -> None:
    _validate_graph(db, definition, payload)
    _persist_graph(db, definition, payload, disable_omitted_transitions=disable_omitted_transitions)
    definition.version = (definition.version or 1) + 1
    definition.update_time = datetime.now()
    db.commit()
    db.refresh(definition)


def apply_template(db: Session, definition_id: int) -> dict:
    definition = _get_definition(db, definition_id)
    template_definition = _system_template_definition(db, definition.object_type)
    if template_definition.id == definition.id:
        return _graph_response(db, definition)
    payload = _template_graph_payload_from_definition(db, definition, template_definition)
    payload = _synchronize_transition_state_availability(db, definition, payload)
    _save_graph(db, definition, payload, disable_omitted_transitions=True)
    return _graph_response(db, definition)


def preview_template(db: Session, definition_id: int) -> dict:
    definition = _get_definition(db, definition_id)
    template_definition = _system_template_definition(db, definition.object_type)
    if template_definition.id == definition.id:
        return _graph_response(db, definition)
    payload = _template_graph_payload_from_definition(db, definition, template_definition)
    return {
        "definition": WorkflowDefinitionRead.model_validate(definition).model_copy(
            update={"initial_state_id": payload.initial_state_id}
        ),
        "states": [item.model_dump() for item in payload.states],
        "transitions": [item.model_dump() for item in payload.transitions],
    }


def _system_template_definition(db: Session, object_type: str) -> WorkflowDefinition:
    ensure_default_workflow_templates(db, reconcile_existing=False)
    definitions = (
        db.query(WorkflowDefinition)
        .filter(
            WorkflowDefinition.object_type == object_type,
            WorkflowDefinition.scope_type == "system",
            WorkflowDefinition.is_default_template.is_(True),
            WorkflowDefinition.enabled.is_(True),
        )
        .order_by(WorkflowDefinition.id.asc())
        .all()
    )
    if len(definitions) != 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Expected exactly one system workflow template for {object_type}",
        )
    return definitions[0]


def _template_graph_payload_from_definition(
    db: Session,
    definition: WorkflowDefinition,
    template_definition: WorkflowDefinition,
) -> WorkflowTemplateGraphSave:
    template_states = (
        db.query(WorkflowState)
        .filter(WorkflowState.definition_id == template_definition.id)
        .order_by(WorkflowState.sort_order.asc(), WorkflowState.id.asc())
        .all()
    )
    existing_states = (
        db.query(WorkflowState)
        .filter(WorkflowState.definition_id == definition.id)
        .order_by(WorkflowState.id.asc())
        .all()
    )
    existing_by_role: dict[str, list[WorkflowState]] = defaultdict(list)
    existing_by_name: dict[tuple[str, str], list[WorkflowState]] = defaultdict(list)
    for state in existing_states:
        if state.state_role:
            existing_by_role[state.state_role].append(state)
        existing_by_name[(state.status_name, state.category)].append(state)

    source_to_input_id: dict[int, int] = {}
    states = []
    next_temp_id = -1
    for source_state in template_states:
        matches = existing_by_role[source_state.state_role] if source_state.state_role else []
        if not matches:
            matches = existing_by_name[(source_state.status_name, source_state.category)]
        if len(matches) > 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Ambiguous template state: {source_state.status_name}",
            )
        input_id = matches[0].id if matches else next_temp_id
        if not matches:
            next_temp_id -= 1
        source_to_input_id[source_state.id] = input_id
        states.append(
            {
                "id": input_id,
                "status_name": source_state.status_name,
                "category": source_state.category,
                "state_role": source_state.state_role,
                "terminal_kind": source_state.terminal_kind,
                "color": source_state.color,
                "x": source_state.x,
                "y": source_state.y,
                "sort_order": source_state.sort_order,
                "enabled": source_state.enabled,
            }
        )

    template_transitions = (
        db.query(WorkflowTransition)
        .filter(WorkflowTransition.definition_id == template_definition.id)
        .order_by(WorkflowTransition.sort_order.asc(), WorkflowTransition.id.asc())
        .all()
    )
    existing_transitions = (
        db.query(WorkflowTransition)
        .filter(WorkflowTransition.definition_id == definition.id)
        .order_by(WorkflowTransition.sort_order.asc(), WorkflowTransition.id.asc())
        .all()
    )
    existing_transition_ids = _match_template_transition_ids(
        template_transitions,
        existing_transitions,
        source_to_input_id,
    )
    role_refs_by_transition: dict[int, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    if template_transitions:
        for role_ref in (
            db.query(WorkflowTransitionRole)
            .filter(WorkflowTransitionRole.transition_id.in_([item.id for item in template_transitions]))
            .order_by(WorkflowTransitionRole.sort_order.asc(), WorkflowTransitionRole.id.asc())
            .all()
        ):
            role_refs_by_transition[role_ref.transition_id][role_ref.purpose].append(role_ref.role_id)

    transitions = []
    for source_transition in template_transitions:
        ui_config = deepcopy(source_transition.ui_config)
        if isinstance(ui_config, dict):
            ui_config.pop("list_priority", None)
        role_refs = role_refs_by_transition[source_transition.id]
        transitions.append(
            {
                "id": existing_transition_ids.get(source_transition.id),
                "action_key": source_transition.action_key,
                "action_name": source_transition.action_name,
                "from_state_id": source_to_input_id[source_transition.from_state_id],
                "to_state_id": source_to_input_id[source_transition.to_state_id],
                "allowed_roles": source_transition.allowed_roles,
                "allowed_role_ids": list(role_refs.get("allowed", [])),
                "handler_target_role_ids": list(role_refs.get("target", [])),
                "handler_fallback_role_ids": list(role_refs.get("fallback", [])),
                "handler_rule": deepcopy(source_transition.handler_rule),
                "trigger_config": deepcopy(source_transition.trigger_config),
                "condition_config": _remap_condition_state_ids(
                    source_transition.condition_config,
                    source_to_input_id,
                ),
                "validator_config": deepcopy(source_transition.validator_config),
                "post_action_config": deepcopy(source_transition.post_action_config),
                "ui_config": ui_config,
                "form_config": deepcopy(source_transition.form_config),
                "diagram_config": deepcopy(source_transition.diagram_config),
                "enabled": source_transition.enabled,
                "auto_disabled_by_state": source_transition.auto_disabled_by_state,
                "sort_order": source_transition.sort_order,
            }
        )
    payload = WorkflowTemplateGraphSave.model_validate(
        {
            "initial_state_id": source_to_input_id.get(template_definition.initial_state_id),
            "states": states,
            "transitions": transitions,
        }
    )
    for transition in payload.transitions:
        _normalize_legacy_transition_role_references(db, transition)
    return payload


def _match_template_transition_ids(
    template_transitions: list[WorkflowTransition],
    existing_transitions: list[WorkflowTransition],
    source_to_input_id: dict[int, int],
) -> dict[int, int]:
    source_groups = _workflow_transition_groups_for_template(
        template_transitions,
        lambda item: (item.action_key, source_to_input_id[item.from_state_id]),
    )
    target_groups = _workflow_transition_groups_for_template(
        existing_transitions,
        lambda item: (item.action_key, item.from_state_id),
    )
    matches: dict[int, int] = {}
    for key, source_group in source_groups.items():
        target_group = target_groups.get(key, [])
        for source_transition, target_transition in _pair_transitions_by_target_state(
            source_group,
            target_group,
            source_to_input_id,
        ):
            matches[source_transition.id] = target_transition.id
    return matches


def _workflow_transition_groups_for_template(items, identity) -> dict[tuple, list[WorkflowTransition]]:
    grouped: dict[tuple, list[WorkflowTransition]] = defaultdict(list)
    for item in items:
        grouped[identity(item)].append(item)
    for group in grouped.values():
        group.sort(key=lambda item: (not item.enabled, item.sort_order, item.id))
    return dict(grouped)


def _pair_transitions_by_target_state(
    source_group: list[WorkflowTransition],
    target_group: list[WorkflowTransition],
    source_to_target_state_id: dict[int, int],
) -> list[tuple[WorkflowTransition, WorkflowTransition]]:
    target_by_state_id: dict[int, list[WorkflowTransition]] = defaultdict(list)
    for transition in target_group:
        target_by_state_id[transition.to_state_id].append(transition)
    matched_target_ids: set[int] = set()
    matched_source_ids: set[int] = set()
    matches = []
    for source_transition in source_group:
        target_candidates = target_by_state_id.get(
            source_to_target_state_id[source_transition.to_state_id],
            [],
        )
        target_transition = next(
            (item for item in target_candidates if item.id not in matched_target_ids),
            None,
        )
        if target_transition is not None:
            matches.append((source_transition, target_transition))
            matched_source_ids.add(source_transition.id)
            matched_target_ids.add(target_transition.id)
    remaining_sources = [item for item in source_group if item.id not in matched_source_ids]
    remaining_targets = [item for item in target_group if item.id not in matched_target_ids]
    matches.extend(zip(remaining_sources, remaining_targets))
    return matches


def _get_definition(db: Session, definition_id: int) -> WorkflowDefinition:
    definition = db.query(WorkflowDefinition).filter(WorkflowDefinition.id == definition_id).first()
    if not definition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow definition not found")
    return definition


def _validate_definition_payload(
    db: Session,
    data: dict,
    *,
    excluding_definition_id: int | None = None,
) -> None:
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
        if data.get("enabled", True):
            conflicts_query = db.query(WorkflowDefinition).filter(
                WorkflowDefinition.scope_type == "assignee_rule_config",
                WorkflowDefinition.scope_id == data["scope_id"],
                WorkflowDefinition.object_type == data["object_type"],
                WorkflowDefinition.enabled.is_(True),
            )
            if excluding_definition_id is not None:
                conflicts_query = conflicts_query.filter(WorkflowDefinition.id != excluding_definition_id)
            conflicts = conflicts_query.order_by(WorkflowDefinition.id.asc()).all()
            if conflicts:
                object_label = {
                    "requirement": "需求",
                    "task": "任务",
                    "bug": "Bug",
                    "iteration": "迭代",
                    "project": "项目",
                }.get(data["object_type"], data["object_type"])
                definitions = "、".join(f"ID {item.id}（{item.name}）" for item in conflicts)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"工作流方案 {data['scope_id']} 已存在启用的 {object_label} 工作流定义：{definitions}；"
                        "请先停用冲突定义后再创建或启用。"
                    ),
                )


def _validate_graph(db: Session, definition: WorkflowDefinition, payload: WorkflowGraphSave) -> None:
    if definition.object_type not in OBJECT_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown workflow object type")
    state_ids: set[int] = set()
    state_roles: set[str] = set()
    states_by_id = {}
    for state in payload.states:
        if state.category not in STATE_CATEGORIES:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown state category")
        if state.terminal_kind and state.terminal_kind not in TERMINAL_KINDS:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown terminal kind")
        if state.category == "terminal" and not state.terminal_kind:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Terminal kind is required for a terminal state",
            )
        if state.category != "terminal" and state.terminal_kind is not None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Terminal kind requires a terminal state")
        if state.state_role is not None:
            if definition.object_type not in WORK_ITEM_STATE_ROLE_OBJECT_TYPES:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="State role is not supported for this workflow type")
            if state.state_role not in WORK_ITEM_STATE_ROLES:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported work-item state role")
            if state.state_role in state_roles:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Duplicate work-item state role")
            state_roles.add(state.state_role)
        if state.id in state_ids:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Duplicate state id")
        state_ids.add(state.id)
        states_by_id[state.id] = state
    if payload.states and payload.initial_state_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Initial state is required")
    if payload.initial_state_id is not None and payload.initial_state_id not in state_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Initial state is not in this graph")
    initial = next((item for item in payload.states if item.id == payload.initial_state_id), None)
    if initial and not initial.enabled:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Initial state must be enabled")
    transition_ids: set[int] = set()
    transition_names: set[tuple[int, str]] = set()
    for transition in payload.transitions:
        if transition.id is not None and transition.id > 0:
            if transition.id in transition_ids:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Duplicate transition id")
            transition_ids.add(transition.id)
        if transition.from_state_id not in state_ids or transition.to_state_id not in state_ids:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Transition references unknown state")
        name_key = (transition.from_state_id, transition.action_name.strip())
        if transition.enabled and name_key in transition_names:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Duplicate enabled transition name for source state",
            )
        if transition.enabled:
            transition_names.add(name_key)
        _validate_roles(transition.allowed_roles)
        _validate_role_ids(db, transition.allowed_role_ids, "Allowed role")
        _validate_handler_rule(
            db,
            transition.handler_rule,
            transition.handler_target_role_ids,
            transition.handler_fallback_role_ids,
        )
        _validate_condition_config(db, transition.condition_config, state_ids)
        _validate_form_config(transition.form_config)
        _validate_typed_config(transition.validator_config, VALIDATOR_TYPES, "validator")
        _validate_ui_config(transition.ui_config)
        transition.diagram_config = _normalize_generated_diagram_config(
            transition.diagram_config,
            states_by_id[transition.from_state_id],
            states_by_id[transition.to_state_id],
        )
        _validate_diagram_config(
            transition.diagram_config,
            states_by_id[transition.from_state_id],
            states_by_id[transition.to_state_id],
        )
        _validate_automation_config(transition.trigger_config, "trigger")
        _validate_automation_config(transition.post_action_config, "post action")


def _validate_handler_rule(
    db: Session,
    handler_rule: dict | None,
    target_role_ids: list[int],
    fallback_role_ids: list[int],
) -> None:
    if not handler_rule:
        return
    target_type = handler_rule.get("target_type", "keep_current")
    fallback_type = handler_rule.get("fallback_type", "keep_current")
    if target_type not in HANDLER_SOURCE_TYPES or fallback_type not in HANDLER_SOURCE_TYPES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown handler source type")
    if target_type in {"project_role", "fixed_role"} and not target_role_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Target roles are required")
    if fallback_type in {"project_role", "fixed_role"} and not fallback_role_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Fallback roles are required")
    _validate_role_ids(db, target_role_ids, "Target role")
    _validate_role_ids(db, fallback_role_ids, "Fallback role")


def _validate_roles(value) -> None:
    identities = set(_csv(value).split(",")) - {""}
    if not identities:
        return
    unknown = identities - IDENTITY_ROLES
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown workflow role(s): {', '.join(sorted(unknown))}",
        )


def _validate_role_ids(db: Session, role_ids: list[int], label: str) -> None:
    unique_ids = set(role_ids)
    if len(unique_ids) != len(role_ids) or any(role_id <= 0 for role_id in unique_ids):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid {label.lower()} IDs")
    if not unique_ids:
        return
    persisted_ids = {
        role_id
        for (role_id,) in db.query(Role.id).filter(Role.id.in_(unique_ids), Role.enabled.is_(True)).all()
    }
    unknown_ids = unique_ids - persisted_ids
    if unknown_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown {label.lower()} ID(s): {', '.join(str(item) for item in sorted(unknown_ids))}",
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
    _validate_role_ids(db, config.get("allow_override_role_ids") or [], "Override role")


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
    if config and config.get("list_display", "more") not in {"primary", "more"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported button group")


def _diagram_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="图形路径无效，请恢复自动布线或重新绘制路径",
    )


def _normalize_generated_diagram_config(config: dict | None, from_state, to_state) -> dict | None:
    if not isinstance(config, dict) or config.get("routing_mode") != "generated":
        return config
    try:
        _validate_diagram_config(config, from_state, to_state)
    except HTTPException:
        # Generated paths can become stale when an editor changes a transition endpoint.
        # A null route makes the client regenerate it for the current endpoints.
        return None
    return config


def _validate_diagram_config(config: dict | None, from_state, to_state) -> None:
    if not config:
        return
    expected_keys = {
        "version", "routing_mode", "source_anchor", "target_anchor", "waypoints",
    }
    if not isinstance(config, dict) or set(config) != expected_keys:
        raise _diagram_error()
    if config["version"] != 1 or config["routing_mode"] not in {"manual", "generated"}:
        raise _diagram_error()

    anchors = []
    for key, node in (("source_anchor", from_state), ("target_anchor", to_state)):
        anchor = config[key]
        if not isinstance(anchor, dict) or set(anchor) != {"side", "ratio"}:
            raise _diagram_error()
        ratio = anchor["ratio"]
        if (
            anchor["side"] not in DIAGRAM_SIDES
            or isinstance(ratio, bool)
            or not isinstance(ratio, (int, float))
            or not isfinite(ratio)
            or not 0 <= ratio <= 1
        ):
            raise _diagram_error()
        anchors.append(_diagram_anchor_point(node, anchor["side"], ratio))

    waypoints = config["waypoints"]
    if not isinstance(waypoints, list) or len(waypoints) > MAX_DIAGRAM_WAYPOINTS:
        raise _diagram_error()
    points = []
    for waypoint in waypoints:
        if not isinstance(waypoint, dict) or set(waypoint) != {"x", "y"}:
            raise _diagram_error()
        x = waypoint["x"]
        y = waypoint["y"]
        if (
            isinstance(x, bool)
            or isinstance(y, bool)
            or not isinstance(x, (int, float))
            or not isinstance(y, (int, float))
            or not isfinite(x)
            or not isfinite(y)
        ):
            raise _diagram_error()
        points.append((x, y))

    route = [anchors[0], *points, anchors[1]]
    for start, end in zip(route, route[1:]):
        if start == end or (start[0] != end[0] and start[1] != end[1]):
            raise _diagram_error()


def _diagram_anchor_point(node, side: str, ratio: float) -> tuple[float, float]:
    if side in {"top", "bottom"}:
        raw_x = node.x + DIAGRAM_NODE_WIDTH * ratio
        x = min(max(raw_x, node.x + DIAGRAM_CORNER_GUARD), node.x + DIAGRAM_NODE_WIDTH - DIAGRAM_CORNER_GUARD)
        y = node.y if side == "top" else node.y + DIAGRAM_NODE_HEIGHT
        return x, y
    raw_y = node.y + DIAGRAM_NODE_HEIGHT * ratio
    y = min(max(raw_y, node.y + DIAGRAM_CORNER_GUARD), node.y + DIAGRAM_NODE_HEIGHT - DIAGRAM_CORNER_GUARD)
    x = node.x if side == "left" else node.x + DIAGRAM_NODE_WIDTH
    return x, y


def _validate_automation_config(config: dict | list | None, label: str) -> None:
    if not config:
        return
    entries = config if isinstance(config, list) else [config]
    for item in entries:
        if not isinstance(item, dict) or item.get("type") not in AUTOMATION_TYPES:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unsupported {label} type")
        if item.get("type") == "system_action":
            continue
        if item.get("receiver") not in NOTIFICATION_RECEIVERS or not str(item.get("title") or "").strip():
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid {label} notification")


def _persist_graph(
    db: Session,
    definition: WorkflowDefinition,
    payload: WorkflowGraphSave,
    *,
    disable_omitted_transitions: bool = False,
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
            if "state_role" not in item.model_fields_set:
                data.pop("state_role")
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
        data = item.model_dump(exclude={"id", "from_state_id", "to_state_id", "action_key", "allowed_role_ids", "handler_target_role_ids", "handler_fallback_role_ids"})
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
            transition = WorkflowTransition(
                definition_id=definition.id,
                action_key=getattr(item, "action_key", None) or f"custom_{uuid4().hex}",
                **data,
            )
            db.add(transition)
        transition.from_state_id = from_state_id
        transition.to_state_id = to_state_id
        persisted_transitions.append(transition)
    db.flush()
    for item, transition in zip(payload.transitions, persisted_transitions):
        submitted_role_fields = {
            "allowed_role_ids", "handler_target_role_ids", "handler_fallback_role_ids",
        } & item.model_fields_set
        if not submitted_role_fields and item.id is not None and item.id > 0:
            continue
        role_refs = [
            ("allowed", item.allowed_role_ids),
            ("target", item.handler_target_role_ids),
            ("fallback", item.handler_fallback_role_ids),
        ]
        db.query(WorkflowTransitionRole).filter(WorkflowTransitionRole.transition_id == transition.id).delete()
        for purpose, role_ids in role_refs:
            db.add_all(WorkflowTransitionRole(transition_id=transition.id, role_id=role_id, purpose=purpose, sort_order=index) for index, role_id in enumerate(role_ids))

    omitted_transition_ids = set(existing_transitions) - submitted_transition_ids
    if omitted_transition_ids:
        if disable_omitted_transitions:
            for transition_id in omitted_transition_ids:
                existing_transitions[transition_id].enabled = False
            omitted_transition_ids = set()
    if omitted_transition_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Persisted workflow transitions cannot be deleted; disable them instead",
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


def _template_graph_payload(db: Session, definition: WorkflowDefinition, template) -> WorkflowTemplateGraphSave:
    existing_by_identity: dict[tuple[str, str], list[WorkflowState]] = defaultdict(list)
    existing_states = (
        db.query(WorkflowState)
        .filter(WorkflowState.definition_id == definition.id)
        .order_by(WorkflowState.id.asc())
        .all()
    )
    for state in existing_states:
        existing_by_identity[(state.status_name, state.category)].append(state)
    ref_to_input_id: dict[str, int] = {}
    states = []
    next_temp_id = -1
    for item in template.states:
        matches = existing_by_identity[(item.status_name, item.category)]
        enabled_matches = [state for state in matches if state.enabled]
        if len(enabled_matches) > 1 or (not enabled_matches and len(matches) > 1):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Ambiguous template state: {item.status_name}",
            )
        candidate = enabled_matches[0] if enabled_matches else (matches[0] if matches else None)
        if candidate:
            input_id = candidate.id
        else:
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
        _resolve_template_role_references(db, data)
        transitions.append(data)
    initial = next((item for item in template.states if item.category == "start"), None)
    return WorkflowTemplateGraphSave(
        initial_state_id=ref_to_input_id[initial.ref] if initial else None,
        states=states,
        transitions=transitions,
    )


def _resolve_template_role_references(db: Session, data: dict) -> None:
    identities, role_ids = _template_role_values(db, data.get("allowed_roles"))
    data["allowed_roles"] = ",".join(identities)
    data["allowed_role_ids"] = role_ids
    rule = dict(data.get("handler_rule") or {})
    for field, target_field in (("target_roles", "handler_target_role_ids"), ("fallback_roles", "handler_fallback_role_ids")):
        _identities, ids = _template_role_values(db, rule.pop(field, ""))
        data[target_field] = ids
    data["handler_rule"] = rule or None
    condition = data.get("condition_config")
    if isinstance(condition, dict) and "allow_override_roles" in condition:
        condition = dict(condition)
        _identities, ids = _template_role_values(db, condition.pop("allow_override_roles"))
        condition["allow_override_role_ids"] = ids
        data["condition_config"] = condition


def _template_role_values(db: Session, value) -> tuple[list[str], list[int]]:
    identities: list[str] = []
    role_ids: list[int] = []
    for name in _csv(value).split(","):
        if not name:
            continue
        if name in IDENTITY_ROLES:
            identities.append(name)
            continue
        candidates = TEMPLATE_CAPABILITY_ALIASES.get(name, (name,))
        role_id = None
        for capability in candidates:
            role_id = db.query(RoleCapability.role_id).filter(RoleCapability.capability == capability).scalar()
            if role_id is not None:
                break
        if role_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Default workflow role is not configured: {name}",
            )
        role_ids.append(int(role_id))
    return list(dict.fromkeys(identities)), list(dict.fromkeys(role_ids))


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
    role_refs = {}
    for ref in db.query(WorkflowTransitionRole).filter(WorkflowTransitionRole.transition_id.in_([item.id for item in transitions])).all():
        role_refs.setdefault((ref.transition_id, ref.purpose), []).append(ref.role_id)
    for transition in transitions:
        transition.allowed_role_ids = role_refs.get((transition.id, "allowed"), [])
        transition.handler_target_role_ids = role_refs.get((transition.id, "target"), [])
        transition.handler_fallback_role_ids = role_refs.get((transition.id, "fallback"), [])
    return {"definition": definition, "states": states, "transitions": transitions}


def _csv(value) -> str:
    if isinstance(value, list):
        return ",".join(str(item).strip() for item in value if str(item).strip())
    return ",".join(str(item).strip() for item in str(value or "").split(",") if str(item).strip())
