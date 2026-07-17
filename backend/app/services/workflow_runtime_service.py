from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.assignee_rule_config import AssigneeRuleConfig
from app.models.bug import Bug
from app.models.iteration import Iteration, IterationProject
from app.models.notification import Notification
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.relation import ObjectRelation
from app.models.requirement import Requirement
from app.models.status_operation import StatusOperationLog
from app.models.task import Task
from app.models.test_case import TestCase
from app.models.test_case_execution import TestCaseExecutionLog
from app.models.test_run import TestRun, TestRunCase
from app.models.user import User
from app.models.workflow_definition import WorkflowDefinition, WorkflowState, WorkflowTransition
from app.services.default_workflow_template_service import ensure_default_workflow_templates
from app.services.bug_type_service import bug_type_options, get_enabled_bug_type
from app.services.project_permission_service import (
    actor_role_keys,
    can_admin_action,
    ensure_authenticated,
    is_project_member,
    is_project_owner,
    is_system_admin,
)
from app.services.status_operation_service import create_status_operation
from app.services.workflow_state_query_service import current_state_name, is_terminal_state
from app.views.status_operation_view import StatusOperationCreate
from app.views.workflow_runtime_view import (
    WorkflowTransitionActionRead,
    WorkflowTransitionBatchRead,
    WorkflowTransitionBatchRequest,
    WorkflowTransitionBatchResultItem,
    WorkflowTransitionExecuteRead,
    WorkflowTransitionExecuteRequest,
)


MODEL_BY_TYPE = {
    "requirement": Requirement,
    "task": Task,
    "bug": Bug,
    "iteration": Iteration,
    "project": Project,
}

SUPPORTED_VALIDATOR_TYPES = {
    "bug_close_gate", "requirement_terminal_gate", "iteration_terminal_gate", "project_close_gate",
}
SUPPORTED_AUTOMATION_TYPES = {"notification"}
def list_available_transitions(
    db: Session,
    object_type: str,
    object_id: int,
    actor: User | None,
) -> list[WorkflowTransitionActionRead]:
    ensure_default_workflow_templates(db)
    item = _get_item(db, object_type, object_id)
    definition_context = _resolve_definition_context(db, object_type, item)
    if not definition_context:
        return []
    definition, current_state = definition_context
    query = db.query(WorkflowTransition).filter(
        WorkflowTransition.definition_id == definition.id,
        WorkflowTransition.enabled == True,  # noqa: E712
    )
    query = query.filter(WorkflowTransition.from_state_id == current_state.id)
    transitions = query.order_by(WorkflowTransition.sort_order.asc(), WorkflowTransition.id.asc()).all()
    result = []
    for transition in transitions:
        if not _matches_transition_condition(item, transition):
            continue
        if not _can_see_transition(db, object_type, item, transition, actor):
            continue
        result.append(_transition_read(db, transition))
    return result


def batch_available_transitions(
    db: Session,
    payload: WorkflowTransitionBatchRequest,
    actor: User | None,
) -> WorkflowTransitionBatchRead:
    return WorkflowTransitionBatchRead(
        items=[
            WorkflowTransitionBatchResultItem(
                object_type=item.object_type,
                id=item.id,
                transitions=list_available_transitions(db, item.object_type, item.id, actor),
            )
            for item in payload.items
        ]
    )


def execute_transition(
    db: Session,
    object_type: str,
    object_id: int,
    request: WorkflowTransitionExecuteRequest,
    actor: User | None,
):
    ensure_authenticated(actor)
    ensure_default_workflow_templates(db)
    item = _get_item(db, object_type, object_id)
    transition_context = _get_executable_transition(db, object_type, item, request.action_key)
    transition, current_state = transition_context
    _ensure_supported_runtime_configuration(transition)
    from_status = current_state.status_name
    _ensure_can_execute(db, object_type, item, transition, actor, request)
    if (transition.ui_config or {}).get("command_type"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Non-status command must use its dedicated endpoint")

    delegated = _is_delegated(db, item, actor)
    delegated_owner = _owner_user(db, getattr(item, "owner_id", None)) if delegated else None
    original_owner_id = getattr(item, "owner_id", None)
    selected_values = _selected_values(request)
    default_target_state, resolved_target_state = _resolve_target_states(
        db,
        object_type,
        item,
        transition,
        request,
        actor,
        selected_values,
    )
    default_target_status = default_target_state.status_name
    resolved_target_status = resolved_target_state.status_name
    if object_type == "bug" and transition.action_key == "reclassify_bug_type":
        if not (request.payload.get("reason") or "").strip():
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Reclassification reason is required")
        selected_values.update(
            {
                "old_bug_type": getattr(item, "bug_type", None),
                "new_bug_type": selected_values.get("bug_type"),
                "old_status": from_status,
                "default_target_status": default_target_status,
                "resolved_target_status": resolved_target_status,
            }
        )
    _apply_domain_payload(db, object_type, item, transition, request, actor, selected_values)
    _run_transition_validator(db, object_type, item, transition, resolved_target_state)
    automation_results = _run_transition_automations(
        db,
        transition.trigger_config,
        "trigger",
        object_type,
        item,
        actor,
        None,
        transition,
    )
    item.workflow_definition_id = transition.definition_id
    item.current_state_id = resolved_target_state.id
    handler_routing = _next_owner_resolution(
        db,
        object_type,
        item,
        transition,
        request,
        actor,
        transition.action_key,
    )
    next_owner_id = handler_routing["final_owner_id"]
    if (
        transition.action_key == "submit_confirmation"
        and next_owner_id is None
        and not (transition.handler_rule or {}).get("allow_unassigned_confirmation", False)
    ):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Confirmation handler is required")
    if hasattr(item, "owner_id") and next_owner_id != original_owner_id:
        item.owner_id = next_owner_id
    if handler_routing["source_rule"] != "keep_current" or next_owner_id != original_owner_id:
        selected_values["handler_routing"] = handler_routing
    next_owner = _owner_user(db, next_owner_id) if next_owner_id else None
    automation_results.extend(
        _run_transition_automations(
            db,
            transition.post_action_config,
            "post_action",
            object_type,
            item,
            actor,
            next_owner_id,
            transition,
        )
    )
    if automation_results:
        selected_values["automation_results"] = automation_results
    operation = create_status_operation(
        db,
        object_type=object_type,
        object_id=item.id,
        action=transition.action_key,
        from_status=from_status,
        to_status=resolved_target_status,
        workflow_definition_id=transition.definition_id,
        from_state_id=current_state.id,
        to_state_id=resolved_target_state.id,
        from_state_name=current_state.status_name,
        to_state_name=resolved_target_state.status_name,
        payload=_status_payload(request),
        actor_id=actor.id if actor else None,
        actor_name=actor.full_name if actor else None,
        is_delegated=delegated,
        delegated_owner_id=delegated_owner.id if delegated_owner else getattr(item, "owner_id", None) if delegated else None,
        delegated_owner_name=delegated_owner.full_name if delegated_owner else None,
        delegate_reason=request.delegate_reason,
        selected_values=selected_values,
        default_target_status=default_target_status,
        resolved_target_status=resolved_target_status,
        override_reason=request.override_reason or request.payload.get("override_reason"),
        next_owner_id=next_owner_id,
        next_owner_name=next_owner.full_name if next_owner else None,
    )
    if next_owner_id != original_owner_id:
        target_type = (transition.handler_rule or {}).get("target_type", "keep_current")
        operation.reason = operation.reason or request.delegate_reason or transition.action_key
        operation.remark = _append_remark(
            operation.remark,
            f"handler transition ({target_type}): {original_owner_id} -> {next_owner_id}",
        )
    db.commit()
    db.refresh(item)
    return WorkflowTransitionExecuteRead(
        object_type=object_type,
        id=item.id,
        workflow_definition_id=item.workflow_definition_id,
        current_state_id=item.current_state_id,
        status_name=resolved_target_state.status_name,
        state_category=resolved_target_state.category,
        owner_id=getattr(item, "owner_id", None),
        default_target_status=default_target_status,
        resolved_target_status=resolved_target_status,
        default_target_state_id=default_target_state.id if default_target_state else None,
        resolved_target_state_id=resolved_target_state.id if resolved_target_state else None,
        selected_values=selected_values,
        override_reason=request.override_reason or request.payload.get("override_reason"),
    )


def _get_item(db: Session, object_type: str, object_id: int):
    model = MODEL_BY_TYPE.get(object_type)
    if not model:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported workflow object type")
    item = db.query(model).filter(model.id == object_id, getattr(model, "deleted", 0) == 0).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow object not found")
    return item


def _resolve_definition_context(db: Session, object_type: str, item):
    definition = db.query(WorkflowDefinition).filter(
        WorkflowDefinition.id == item.workflow_definition_id,
        WorkflowDefinition.object_type == object_type,
    ).first()
    state_record = db.query(WorkflowState).filter(
        WorkflowState.id == item.current_state_id,
        WorkflowState.definition_id == item.workflow_definition_id,
    ).first()
    if not definition or not state_record:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{object_type} {item.id} has invalid workflow state references",
        )
    return definition, state_record


def _get_executable_transition(db: Session, object_type: str, item, action_key: str):
    definition, current_state = _resolve_definition_context(db, object_type, item)
    transitions = (
        db.query(WorkflowTransition)
        .filter(
            WorkflowTransition.definition_id == definition.id,
            WorkflowTransition.from_state_id == current_state.id,
            WorkflowTransition.action_key == action_key,
            WorkflowTransition.enabled == True,  # noqa: E712
        )
        .order_by(WorkflowTransition.sort_order.asc(), WorkflowTransition.id.asc())
        .all()
    )
    for transition in transitions:
        if _matches_transition_condition(item, transition):
            return transition, current_state
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Workflow transition not available")


def _transition_read(db: Session, transition: WorkflowTransition) -> WorkflowTransitionActionRead:
    ui_config = transition.ui_config or {}
    form_config = dict(transition.form_config or {})
    fields = [dict(field) for field in form_config.get("fields") or []]
    for field in fields:
        if field.get("field") == "bug_type" and field.get("type") == "select":
            field["options"] = bug_type_options(db)
    if fields:
        form_config["fields"] = fields
    handler_rule = transition.handler_rule or {}
    condition_config = transition.condition_config or {}
    routes = condition_config.get("routes") or {}
    allowed_target_state_ids = sorted({int(value) for value in routes.values()}) if routes else []
    if condition_config.get("route_dictionary") == "bug_type":
        allowed_target_state_ids = sorted(set(_bug_dictionary_target_state_ids(db, transition.definition_id).values()))
    allowed_target_states = (
        db.query(WorkflowState)
        .filter(WorkflowState.id.in_(allowed_target_state_ids))
        .order_by(WorkflowState.id.asc())
        .all()
        if allowed_target_state_ids else []
    )
    if handler_rule.get("allow_manual_owner") and "allow_manual_owner" not in form_config:
        form_config["allow_manual_owner"] = True
    return WorkflowTransitionActionRead(
        action_key=transition.action_key,
        action_name=transition.action_name,
        from_state_id=transition.from_state_id,
        to_state_id=transition.to_state_id,
        button_type=ui_config.get("button_type", "primary"),
        list_display=ui_config.get("list_display", "more"),
        list_priority=int(ui_config.get("list_priority", transition.sort_order or 100)),
        requires_form=bool((form_config.get("fields") or [])),
        confirm_required=bool(ui_config.get("confirm_required", False)),
        routing_mode=condition_config.get("routing_mode"),
        allowed_target_state_ids=allowed_target_state_ids,
        allowed_target_states=[
            {"id": state.id, "status_name": state.status_name}
            for state in allowed_target_states
        ],
        ui_config=ui_config,
        form_config=form_config,
    )


def _matches_transition_condition(item, transition: WorkflowTransition) -> bool:
    condition_config = transition.condition_config or {}
    task_types = condition_config.get("task_types")
    if task_types and getattr(item, "task_type", None) not in task_types:
        return False
    return True


def _can_see_transition(db: Session, object_type: str, item, transition: WorkflowTransition, actor: User | None) -> bool:
    if transition.ui_config and transition.ui_config.get("hidden") is True:
        return False
    if not _matches_ownerless_visibility(object_type, item, transition):
        return False
    if not _handler_allowed(db, object_type, item, transition, actor):
        return False
    return _role_allowed(db, object_type, item, transition, actor)


def _ensure_can_execute(
    db: Session,
    object_type: str,
    item,
    transition: WorkflowTransition,
    actor: User | None,
    request: WorkflowTransitionExecuteRequest,
) -> None:
    delegated = _is_delegated(db, item, actor)
    if not _matches_ownerless_visibility(object_type, item, transition):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Workflow transition not available for current handler state")
    if not _handler_allowed(db, object_type, item, transition, actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only current handler can execute transition")
    if delegated and not request.delegate_reason:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Please provide delegate reason")
    if not _role_allowed(db, object_type, item, transition, actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Transition role not allowed")
    if (transition.handler_rule or {}).get("target_type") == "explicit_owner" and not request.next_owner_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Next handler is required")
    if transition.action_key == "reactivate" and request.next_owner_id:
        project_id = _project_id_for_item(db, object_type, item)
        if not can_admin_action(db, project_id, actor.id if actor else None):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only project administrators can select a reactivation handler")


def _handler_allowed(
    db: Session,
    object_type: str,
    item,
    transition: WorkflowTransition,
    actor: User | None,
) -> bool:
    scope = (transition.ui_config or {}).get("handler_scope")
    if not actor:
        return object_type in {"iteration", "project"}
    project_id = _project_id_for_item(db, object_type, item)
    if scope == "allowed_identity":
        return True
    if scope == "project_member":
        return is_project_member(db, project_id, actor.id)
    owner_id = getattr(item, "owner_id", None)
    if scope == "current_handler":
        return owner_id == actor.id
    if owner_id:
        return owner_id == actor.id or _is_delegated(db, item, actor)
    if object_type in {"iteration", "project"}:
        return True
    return is_project_member(db, project_id, actor.id) or can_admin_action(db, project_id, actor.id)


def _matches_ownerless_visibility(object_type: str, item, transition: WorkflowTransition) -> bool:
    if object_type not in {"requirement", "task", "bug"}:
        return True
    ui_config = transition.ui_config or {}
    owner_id = getattr(item, "owner_id", None)
    if ui_config.get("ownerless_only") is True:
        return owner_id is None
    if ui_config.get("requires_owner") is True:
        return owner_id is not None
    return True


def _role_allowed(db: Session, object_type: str, item, transition: WorkflowTransition, actor: User | None) -> bool:
    roles = _split_csv(transition.allowed_roles)
    if not roles:
        return True
    if not actor:
        return False
    project_id = _project_id_for_item(db, object_type, item)
    if not project_id:
        return True
    identities = _actor_identities(db, object_type, item, actor)
    effective_roles = actor_role_keys(db, project_id, actor.id) | identities
    if "system_admin" in identities and "project_owner" in roles:
        effective_roles.add("project_owner")
    return bool(set(roles) & effective_roles)


def _actor_identities(db: Session, object_type: str, item, actor: User | None) -> set[str]:
    if not actor:
        return set()
    project_id = _project_id_for_item(db, object_type, item)
    identities: set[str] = set()
    if is_system_admin(db, actor.id):
        identities.add("system_admin")
    if is_project_owner(db, project_id, actor.id):
        identities.add("project_owner")
    if is_project_member(db, project_id, actor.id):
        identities.add("project_member")
    if getattr(item, "owner_id", None) == actor.id:
        identities.update({"current_handler", "owner"})
    if getattr(item, "creator_id", None) == actor.id:
        identities.add("creator")
    if getattr(item, "reporter_id", None) == actor.id:
        identities.add("reporter")
    if getattr(item, "proposer_id", None) == actor.id:
        identities.add("proposer")
    if object_type == "bug" and _is_bug_tester(db, item, actor.id):
        identities.add("tester")
    return identities


def _is_bug_tester(db: Session, bug: Bug, actor_id: int) -> bool:
    if getattr(bug, "verified_by", None) == actor_id:
        return True
    if bug.test_case_id:
        test_case = db.query(TestCase).filter(TestCase.id == bug.test_case_id, TestCase.deleted == 0).first()
        if test_case and test_case.default_tester_id == actor_id:
            return True
    if bug.test_run_id:
        test_run = db.query(TestRun).filter(TestRun.id == bug.test_run_id, TestRun.deleted == 0).first()
        if test_run and test_run.test_owner_id == actor_id:
            return True
    return False


def _is_delegated(db: Session, item, actor: User | None) -> bool:
    if not actor:
        return False
    owner_id = getattr(item, "owner_id", None)
    if owner_id is None:
        return False
    if owner_id == actor.id:
        return False
    project_id = _project_id_for_item(db, _object_type_for_item(item), item)
    return can_admin_action(db, project_id, actor.id)


def _selected_values(request: WorkflowTransitionExecuteRequest) -> dict[str, Any]:
    if request.selected_values:
        return dict(request.selected_values)
    return dict(request.payload.get("selected_values") or {})


def _resolve_target_states(
    db: Session,
    object_type: str,
    item,
    transition: WorkflowTransition,
    request: WorkflowTransitionExecuteRequest,
    actor: User | None,
    selected_values: dict[str, Any],
) -> tuple[WorkflowState, WorkflowState]:
    default_target_state_id = transition.to_state_id
    resolved_target_state_id = transition.to_state_id
    condition_config = transition.condition_config or {}

    owner_targets = condition_config.get("target_state_id_by_owner") or {}
    if owner_targets:
        target_owner_id = request.next_owner_id if request.next_owner_id is not None else getattr(item, "owner_id", None)
        default_target_state_id = owner_targets.get(
            "with_owner" if target_owner_id else "without_owner",
            transition.to_state_id,
        )
        resolved_target_state_id = default_target_state_id

    routes = condition_config.get("routes") or {}
    route_dictionary = condition_config.get("route_dictionary")
    allowed_target_state_ids = {int(value) for value in routes.values()} if routes else set()
    if routes or route_dictionary:
        field_name = condition_config.get("field")
        selected_value = selected_values.get(field_name) if field_name else None
        if selected_value is None and field_name:
            selected_value = request.payload.get(field_name)
            if selected_value is not None:
                selected_values[field_name] = selected_value
        if field_name and selected_value is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field_name} is required")

        if route_dictionary == "bug_type":
            dictionary_item = get_enabled_bug_type(db, str(selected_value))
            dictionary_targets = _bug_dictionary_target_state_ids(db, transition.definition_id)
            default_target_state_id = dictionary_targets[dictionary_item.is_real_bug]
            allowed_target_state_ids = set(dictionary_targets.values())
            selected_values["bug_type_name"] = dictionary_item.display_name
            selected_values["is_real_bug"] = dictionary_item.is_real_bug
            selected_values["dictionary_default_target_state_id"] = default_target_state_id
        else:
            default_target_state_id = routes.get(selected_value)
        if default_target_state_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Workflow routing configuration missing for selected value")
        resolved_target_state_id = default_target_state_id

        selected_target_state_id = request.selected_target_state_id or request.payload.get("selected_target_state_id")
        routing_mode = condition_config.get("routing_mode", "automatic")
        if routing_mode == "automatic" and selected_target_state_id is not None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Automatic routing does not allow a selected target state")
        if routing_mode == "manual_allowed" and selected_target_state_id is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Selected target state is required")
        if selected_target_state_id is not None:
            selected_target_state_id = int(selected_target_state_id)
            if selected_target_state_id not in allowed_target_state_ids:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected target state is not allowed")
            if routing_mode == "automatic_with_override" and selected_target_state_id != default_target_state_id:
                override_roles = set(condition_config.get("allow_override_roles") or [])
                identities = _actor_identities(db, object_type, item, actor)
                if not (override_roles & identities):
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Target state override is not allowed")
                override_reason = request.override_reason or request.payload.get("override_reason")
                if not (override_reason or "").strip():
                    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Target state override reason is required")
            resolved_target_state_id = selected_target_state_id

    return (
        _state_for_id(db, transition.definition_id, int(default_target_state_id)),
        _state_for_id(db, transition.definition_id, int(resolved_target_state_id)),
    )


def _state_for_id(db: Session, definition_id: int, state_id: int) -> WorkflowState:
    state_record = db.query(WorkflowState).filter(
        WorkflowState.id == state_id,
        WorkflowState.definition_id == definition_id,
    ).first()
    if not state_record:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Workflow target state is missing for definition {definition_id}: {state_id}",
        )
    return state_record


def _bug_dictionary_target_state_ids(db: Session, definition_id: int) -> dict[bool, int]:
    action_sources = {
        action_key: state_id
        for action_key, state_id in db.query(
            WorkflowTransition.action_key,
            WorkflowTransition.from_state_id,
        ).filter(
            WorkflowTransition.definition_id == definition_id,
            WorkflowTransition.action_key.in_(("submit_verification", "verification_passed")),
            WorkflowTransition.enabled.is_(True),
        )
    }
    if not action_sources.get("submit_verification") or not action_sources.get("verification_passed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Bug workflow definition {definition_id} has incomplete dictionary routing actions",
        )
    return {
        True: int(action_sources["submit_verification"]),
        False: int(action_sources["verification_passed"]),
    }


def _apply_domain_payload(
    db: Session,
    object_type: str,
    item,
    transition: WorkflowTransition,
    request: WorkflowTransitionExecuteRequest,
    actor: User | None,
    selected_values: dict[str, Any],
) -> None:
    payload = request.payload or {}
    if object_type == "requirement" and transition.action_key == "defer":
        _defer_requirement_links(db, item, payload, actor)
    if object_type == "bug" and transition.action_key in {"confirm_bug_type", "reclassify_bug_type"}:
        bug_type = selected_values.get("bug_type")
        if not bug_type:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="bug_type is required")
        dictionary_item = get_enabled_bug_type(db, str(bug_type))
        selected_values["bug_type_name"] = dictionary_item.display_name
        selected_values["is_real_bug"] = dictionary_item.is_real_bug
        item.bug_type = bug_type
    if object_type == "bug" and transition.action_key == "submit_verification":
        item.resolve_time = _parse_effective_time(payload) or datetime.now()
        item.resolved_by = actor.id if actor else None
    if object_type == "bug" and transition.action_key == "verification_passed":
        item.verify_result = payload.get("verify_result") or "passed"
        item.verify_time = _parse_effective_time(payload) or datetime.now()
        item.verified_by = actor.id if actor else None
        item.close_reason = payload.get("reason") or "verified"
    if object_type == "bug" and transition.action_key == "verification_failed":
        item.verify_result = payload.get("verify_result") or "failed"
        item.verify_time = _parse_effective_time(payload) or datetime.now()
        item.verified_by = actor.id if actor else None
        item.reopen_count = (item.reopen_count or 0) + 1
    if object_type == "bug" and transition.action_key == "activate":
        item.reopen_count = (item.reopen_count or 0) + 1
    if object_type == "iteration":
        effective_time = _parse_effective_time(payload) or datetime.now()
        if transition.action_key == "start":
            item.actual_start_date = effective_time.date()
        elif transition.action_key in {"complete", "cancel"}:
            item.actual_end_date = effective_time.date()


def _run_transition_validator(
    db: Session,
    object_type: str,
    item,
    transition: WorkflowTransition,
    resolved_target_state: WorkflowState | None,
) -> None:
    validators = transition.validator_config if isinstance(transition.validator_config, list) else [transition.validator_config]
    for validator in validators:
        if validator:
            _run_single_transition_validator(db, object_type, item, validator, resolved_target_state)


def _run_single_transition_validator(
    db: Session,
    object_type: str,
    item,
    validator: dict[str, Any],
    resolved_target_state: WorkflowState | None,
) -> None:
    validator_type = validator.get("type")
    if not validator_type:
        return
    if validator_type == "bug_close_gate":
        _require_bug_close_tasks_complete(db, item, validator)
    elif validator_type == "requirement_terminal_gate":
        _require_requirement_relations_complete(db, item, resolved_target_state)
    elif validator_type == "iteration_terminal_gate":
        ensure_iteration_items_complete(db, item.id)
    elif validator_type == "project_close_gate":
        _require_project_items_complete(db, item.id)


def _ensure_supported_runtime_configuration(transition: WorkflowTransition) -> None:
    validators = transition.validator_config if isinstance(transition.validator_config, list) else [transition.validator_config]
    for validator in validators:
        if validator and (not isinstance(validator, dict) or validator.get("type") not in SUPPORTED_VALIDATOR_TYPES):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported workflow validator configuration")
    for label, config in (("trigger", transition.trigger_config), ("post action", transition.post_action_config)):
        entries = config if isinstance(config, list) else [config]
        for entry in entries:
            if entry and (not isinstance(entry, dict) or entry.get("type") not in SUPPORTED_AUTOMATION_TYPES):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Unsupported workflow {label} configuration")


def _run_transition_automations(
    db: Session,
    config: dict | list | None,
    stage: str,
    object_type: str,
    item,
    actor: User | None,
    next_owner_id: int | None,
    transition: WorkflowTransition,
) -> list[dict]:
    entries = config if isinstance(config, list) else [config]
    results: list[dict] = []
    for entry in entries:
        if not entry:
            continue
        receiver_id = _automation_receiver_id(
            db,
            entry.get("receiver"),
            object_type,
            item,
            actor,
            next_owner_id,
        )
        result = {
            "stage": stage,
            "type": entry["type"],
            "receiver": entry.get("receiver"),
            "receiver_id": receiver_id,
        }
        if receiver_id is None:
            result["status"] = "skipped_no_receiver"
            results.append(result)
            continue
        notification = Notification(
            receiver_id=receiver_id,
            title=str(entry["title"]),
            content=entry.get("content"),
            object_type=object_type,
            object_id=item.id,
            category="workflow",
            source_type="workflow_transition",
            source_id=transition.id,
            metadata_json={"stage": stage, "action_key": transition.action_key},
            is_read=False,
        )
        db.add(notification)
        db.flush()
        result.update({"status": "created", "notification_id": notification.id})
        results.append(result)
    return results


def _automation_receiver_id(
    db: Session,
    receiver: str | None,
    object_type: str,
    item,
    actor: User | None,
    next_owner_id: int | None,
) -> int | None:
    if receiver == "actor":
        return actor.id if actor else None
    if receiver == "next_handler":
        return next_owner_id
    if receiver == "current_handler":
        return getattr(item, "owner_id", None)
    if receiver == "creator":
        return getattr(item, "creator_id", None)
    if receiver == "project_owner":
        return _project_owner_id(db, _project_id_for_item(db, object_type, item))
    raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported workflow notification receiver")


def _require_bug_close_tasks_complete(db: Session, bug: Bug, validator: dict[str, Any]) -> None:
    task_ids = {
        relation.target_id
        for relation in db.query(ObjectRelation).filter(
            ObjectRelation.source_type == "bug",
            ObjectRelation.source_id == bug.id,
            ObjectRelation.target_type == "task",
            ObjectRelation.relation_type == "linked_task",
        )
    }
    if bug.task_id:
        task_ids.add(bug.task_id)
    if not task_ids:
        return
    tasks = db.query(Task).filter(Task.id.in_(task_ids), Task.deleted == 0).order_by(Task.id.asc()).all()
    blockers = [task for task in tasks if not is_terminal_state(task)]
    if blockers:
        summaries = ", ".join(f"#{task.id} {task.title} [{current_state_name(task) or '-'}]" for task in blockers)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bug has {len(blockers)} unfinished linked task blocker(s): {summaries}",
        )


def _require_requirement_relations_complete(
    db: Session,
    requirement: Requirement,
    resolved_target_state: WorkflowState | None,
) -> None:
    if not resolved_target_state or resolved_target_state.category != "terminal":
        return
    blocking_tasks = [
        task
        for task in db.query(Task).filter(Task.requirement_id == requirement.id, Task.deleted == 0).all()
        if not is_terminal_state(task)
    ]
    if blocking_tasks:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Requirement has unfinished task blockers")
    blocking_bugs = [
        bug
        for bug in db.query(Bug).filter(Bug.requirement_id == requirement.id, Bug.deleted == 0).all()
        if not is_terminal_state(bug)
    ]
    if blocking_bugs:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Requirement has unclosed bug blockers")


def ensure_iteration_items_complete(db: Session, iteration_id: int) -> None:
    requirements = db.query(Requirement).filter(Requirement.iteration_id == iteration_id, Requirement.deleted == 0).all()
    blocking_messages: list[str] = []
    if any(not is_terminal_state(item) for item in requirements):
        blocking_messages.append("requirement")
    tasks = db.query(Task).filter(Task.iteration_id == iteration_id, Task.deleted == 0).all()
    if any(not is_terminal_state(item) for item in tasks):
        blocking_messages.append("task")
    bugs = db.query(Bug).filter(Bug.iteration_id == iteration_id, Bug.deleted == 0).all()
    if any(not is_terminal_state(item) for item in bugs):
        blocking_messages.append("bug")
    test_runs = db.query(TestRun).filter(TestRun.iteration_id == iteration_id, TestRun.deleted == 0).all()
    if any(not _test_run_is_terminal(item) for item in test_runs):
        blocking_messages.append("test run")
    if blocking_messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Iteration has unfinished {', '.join(blocking_messages)} blockers",
        )


def _require_project_items_complete(db: Session, project_id: int) -> None:
    iterations = (
        db.query(Iteration)
        .join(IterationProject, IterationProject.iteration_id == Iteration.id)
        .filter(IterationProject.project_id == project_id, Iteration.deleted == 0)
        .all()
    )
    blocking_messages: list[str] = []
    if any(not is_terminal_state(item) for item in iterations):
        blocking_messages.append("iteration")
    requirements = db.query(Requirement).filter(Requirement.project_id == project_id, Requirement.deleted == 0).all()
    if any(not is_terminal_state(item) for item in requirements):
        blocking_messages.append("requirement")
    tasks = db.query(Task).filter(Task.project_id == project_id, Task.deleted == 0).all()
    if any(not is_terminal_state(item) for item in tasks):
        blocking_messages.append("task")
    bugs = db.query(Bug).filter(Bug.project_id == project_id, Bug.deleted == 0).all()
    if any(not is_terminal_state(item) for item in bugs):
        blocking_messages.append("bug")
    test_runs = db.query(TestRun).filter(TestRun.project_id == project_id, TestRun.deleted == 0).all()
    if any(not _test_run_is_terminal(item) for item in test_runs):
        blocking_messages.append("test run")
    if blocking_messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Project has unfinished {', '.join(blocking_messages)} blockers",
        )


def _test_run_is_terminal(test_run: TestRun) -> bool:
    return test_run.status in {"finished", "completed", "canceled", "closed"}


def _next_owner_resolution(
    db: Session,
    object_type: str,
    item,
    transition: WorkflowTransition,
    request: WorkflowTransitionExecuteRequest,
    actor: User | None,
    transition_action_key: str,
) -> dict[str, Any]:
    rule = transition.handler_rule or {}
    original_owner_id = getattr(item, "owner_id", None)
    target_type = rule.get("target_type", "keep_current")
    default_owner_id, source_rule = _resolve_handler_source(
        db,
        object_type,
        item,
        target_type,
        rule,
        original_owner_id,
        actor,
        request,
        transition_action_key,
    )
    if default_owner_id is None:
        for fallback in _handler_fallback_chain(rule):
            default_owner_id, source_rule = _resolve_handler_source(
                db,
                object_type,
                item,
                fallback["type"],
                fallback,
                original_owner_id,
                actor,
                request,
                transition_action_key,
            )
            if default_owner_id is not None:
                source_rule = f"fallback:{source_rule}"
                break

    manual_override = False
    final_owner_id = default_owner_id
    if request.next_owner_id and rule.get("allow_manual_owner"):
        _ensure_manual_owner_allowed(db, _project_id_for_item(db, object_type, item), request.next_owner_id, rule)
        final_owner_id = request.next_owner_id
        manual_override = target_type != "explicit_owner"
        if target_type == "explicit_owner":
            default_owner_id = request.next_owner_id
            source_rule = "explicit_owner"

    return {
        "previous_owner_id": original_owner_id,
        "source_rule": source_rule,
        "resolved_default_owner_id": default_owner_id,
        "final_owner_id": final_owner_id,
        "manual_override": manual_override,
        "override_reason": request.override_reason or request.payload.get("override_reason"),
    }


def _handler_fallback_chain(rule: dict[str, Any]) -> list[dict[str, Any]]:
    configured = rule.get("fallback_chain")
    if isinstance(configured, list):
        result = []
        for item in configured:
            result.append({"type": item} if isinstance(item, str) else dict(item))
        return [item for item in result if item.get("type")]
    fallback_type = rule.get("fallback_type", "keep_current")
    return [
        {
            "type": fallback_type,
            "roles": rule.get("fallback_roles", ""),
            "fixed_user_id": rule.get("fallback_user_id"),
        }
    ]


def _resolve_handler_source(
    db: Session,
    object_type: str,
    item,
    source_type: str,
    config: dict[str, Any],
    original_owner_id: int | None,
    actor: User | None,
    request: WorkflowTransitionExecuteRequest,
    transition_action_key: str,
) -> tuple[int | None, str]:
    project_id = _project_id_for_item(db, object_type, item)
    if source_type == "keep_current":
        return original_owner_id, source_type
    if source_type == "none":
        return None, source_type
    if source_type == "actor":
        return (actor.id if actor else original_owner_id), source_type
    if source_type == "explicit_owner":
        return (request.next_owner_id or original_owner_id), source_type
    if source_type == "creator":
        return getattr(item, "creator_id", None), source_type
    if source_type == "proposer":
        return getattr(item, "proposer_id", None), source_type
    if source_type in {"reporter", "bug_reporter"}:
        return getattr(item, "reporter_id", None), source_type
    if source_type == "last_resolver" and object_type == "bug":
        return _last_bug_resolver_id(db, item), source_type
    if source_type == "previous_handler":
        return _previous_handler_id(db, object_type, item, original_owner_id), source_type
    if source_type in {"project_role", "fixed_role"}:
        roles = _split_csv(config.get("target_roles") or config.get("roles"))
        return _first_project_member_id(db, project_id, roles), f"{source_type}:{','.join(roles)}"
    if source_type == "project_owner":
        return _project_owner_id(db, project_id), source_type
    if source_type == "fixed_user":
        return config.get("fixed_user_id"), source_type
    if source_type == "requirement_owner":
        requirement = _task_requirement(db, item) if object_type == "task" else None
        return (requirement.owner_id if requirement else None), source_type
    if source_type == "source_owner" and object_type == "task":
        return _task_source_owner_id(db, item), source_type
    if source_type == "test_executor" and object_type == "bug":
        return _bug_test_executor_id(db, item), source_type
    if source_type == "test_case_default_tester" and object_type == "bug":
        test_case = _bug_test_case(db, item)
        return (test_case.default_tester_id if test_case else None), source_type
    if source_type == "bug_verifier" and object_type == "bug":
        return _bug_verifier_owner(db, item, config)
    if source_type == "bug_verifier_if_pending_verification" and object_type == "bug":
        routes_to_verifier = transition_action_key == "submit_verification"
        if not routes_to_verifier and getattr(item, "bug_type", None):
            routes_to_verifier = not get_enabled_bug_type(db, str(item.bug_type)).is_real_bug
        if not routes_to_verifier:
            return original_owner_id, "keep_current"
        return _bug_verifier_owner(db, item, config)
    if source_type == "task_confirmation" and object_type == "task":
        return _task_confirmation_owner(db, item)
    return original_owner_id, source_type


def _previous_handler_id(db: Session, object_type: str, item, current_owner_id: int | None) -> int | None:
    phase_actions = {
        "task": {"submit_confirmation"},
        "bug": {"submit_verification", "confirm_bug_type", "reclassify_bug_type"},
    }.get(object_type, set())
    operations = (
        db.query(StatusOperationLog)
        .filter(
            StatusOperationLog.object_type == object_type,
            StatusOperationLog.object_id == item.id,
            StatusOperationLog.action.in_(phase_actions),
        )
        .order_by(StatusOperationLog.effective_time.desc(), StatusOperationLog.id.desc())
        .all()
    )
    for operation in operations:
        routing = (operation.selected_values or {}).get("handler_routing")
        if not isinstance(routing, dict):
            continue
        if routing.get("final_owner_id") not in {None, current_owner_id}:
            continue
        previous_owner_id = routing.get("previous_owner_id")
        if previous_owner_id is not None:
            return previous_owner_id
    return None


def _task_confirmation_owner(db: Session, task: Task) -> tuple[int | None, str]:
    if task.task_type == "requirement_implementation":
        requirement = _task_requirement(db, task)
        if requirement and requirement.owner_id:
            return requirement.owner_id, "task_confirmation:requirement_owner"
    if task.task_type == "bug_fix":
        bug = _task_source_bug(db, task)
        if bug and bug.reporter_id:
            return bug.reporter_id, "task_confirmation:bug_reporter"
        if bug and bug.verified_by:
            return bug.verified_by, "task_confirmation:bug_verifier"
    if task.task_type == "test_support":
        owner_id, source = _task_test_owner(db, task)
        if owner_id:
            return owner_id, f"task_confirmation:{source}"
        if task.creator_id:
            return task.creator_id, "task_confirmation:creator"
    if task.task_type == "standalone_operation" and task.creator_id:
        return task.creator_id, "task_confirmation:creator"
    return _project_owner_id(db, _project_id_for_item(db, "task", task)), "task_confirmation:project_owner"


def _bug_verifier_owner(db: Session, bug: Bug, rule: dict[str, Any]) -> tuple[int | None, str]:
    executor_id = _bug_test_executor_id(db, bug)
    if executor_id:
        return executor_id, "bug_verifier:test_executor"
    test_case = _bug_test_case(db, bug)
    if test_case and test_case.default_tester_id:
        return test_case.default_tester_id, "bug_verifier:test_case_default_tester"
    if bug.reporter_id:
        return bug.reporter_id, "bug_verifier:reporter"
    project_tester_id = _project_default_tester_id(db, bug.project_id)
    if project_tester_id:
        return project_tester_id, "bug_verifier:project_tester"
    if rule.get("fixed_user_id"):
        return rule["fixed_user_id"], "bug_verifier:fixed_user"
    return _project_owner_id(db, bug.project_id), "bug_verifier:project_owner"


def _bug_test_case(db: Session, bug: Bug) -> TestCase | None:
    if not bug.test_case_id:
        return None
    return db.query(TestCase).filter(TestCase.id == bug.test_case_id, TestCase.deleted == 0).first()


def _bug_test_executor_id(db: Session, bug: Bug) -> int | None:
    if bug.test_run_id and bug.test_case_id:
        run_case = (
            db.query(TestRunCase)
            .filter(
                TestRunCase.test_run_id == bug.test_run_id,
                TestRunCase.test_case_id == bug.test_case_id,
                TestRunCase.tester_id.isnot(None),
            )
            .order_by(TestRunCase.execute_time.desc(), TestRunCase.id.desc())
            .first()
        )
        if run_case:
            return run_case.tester_id
    if bug.test_case_id:
        execution = (
            db.query(TestCaseExecutionLog)
            .filter(
                TestCaseExecutionLog.test_case_id == bug.test_case_id,
                TestCaseExecutionLog.executor_id.isnot(None),
            )
            .order_by(TestCaseExecutionLog.execute_time.desc(), TestCaseExecutionLog.id.desc())
            .first()
        )
        if execution:
            return execution.executor_id
    return None


def _project_default_tester_id(db: Session, project_id: int | None) -> int | None:
    if not project_id:
        return None
    project = db.query(Project).filter(Project.id == project_id, Project.deleted == 0).first()
    if not project or not project.assignee_rule_config_id:
        return None
    config = db.query(AssigneeRuleConfig).filter(AssigneeRuleConfig.id == project.assignee_rule_config_id).first()
    roles = _split_csv(
        ",".join(
            value
            for value in [
                config.test_case_tester_roles if config else "",
                config.test_run_owner_roles if config else "",
            ]
            if value
        )
    )
    return _first_project_member_id(db, project_id, roles)


def _project_owner_id(db: Session, project_id: int | None) -> int | None:
    if not project_id:
        return None
    project = db.query(Project).filter(Project.id == project_id, Project.deleted == 0).first()
    if project and project.owner_id:
        return project.owner_id
    return _first_project_member_id(db, project_id, ["project_owner"])


def _task_requirement(db: Session, task: Task) -> Requirement | None:
    if not task.requirement_id:
        return None
    return db.query(Requirement).filter(Requirement.id == task.requirement_id, Requirement.deleted == 0).first()


def _task_source_bug(db: Session, task: Task) -> Bug | None:
    direct = db.query(Bug).filter(Bug.task_id == task.id, Bug.deleted == 0).order_by(Bug.id.desc()).first()
    if direct:
        return direct
    source_id = _task_source_relation_id(db, task.id, "bug")
    return db.query(Bug).filter(Bug.id == source_id, Bug.deleted == 0).first() if source_id else None


def _task_source_owner_id(db: Session, task: Task) -> int | None:
    requirement = _task_requirement(db, task)
    if requirement and requirement.owner_id:
        return requirement.owner_id
    bug = _task_source_bug(db, task)
    return bug.owner_id if bug else None


def _task_test_owner(db: Session, task: Task) -> tuple[int | None, str]:
    test_run_id = _task_source_relation_id(db, task.id, "test_run")
    if test_run_id:
        test_run = db.query(TestRun).filter(TestRun.id == test_run_id, TestRun.deleted == 0).first()
        if test_run and test_run.test_owner_id:
            return test_run.test_owner_id, "test_owner"
    test_case_id = _task_source_relation_id(db, task.id, "test_case")
    if test_case_id:
        execution = (
            db.query(TestCaseExecutionLog)
            .filter(TestCaseExecutionLog.test_case_id == test_case_id, TestCaseExecutionLog.executor_id.isnot(None))
            .order_by(TestCaseExecutionLog.execute_time.desc(), TestCaseExecutionLog.id.desc())
            .first()
        )
        if execution:
            return execution.executor_id, "test_executor"
        test_case = db.query(TestCase).filter(TestCase.id == test_case_id, TestCase.deleted == 0).first()
        if test_case and test_case.default_tester_id:
            return test_case.default_tester_id, "test_case_default_tester"
    return None, "test_owner"


def _task_source_relation_id(db: Session, task_id: int, source_type: str) -> int | None:
    relation = (
        db.query(ObjectRelation)
        .filter(
            ObjectRelation.source_type == source_type,
            ObjectRelation.target_type == "task",
            ObjectRelation.target_id == task_id,
            ObjectRelation.relation_type == "linked_task",
        )
        .order_by(ObjectRelation.id.desc())
        .first()
    )
    return relation.source_id if relation else None


def _first_project_member_id(db: Session, project_id: int | None, roles: list[str]) -> int | None:
    if not project_id or not roles:
        return None
    for role in roles:
        member = (
            db.query(ProjectMember)
            .filter(ProjectMember.project_id == project_id, ProjectMember.project_role == role)
            .order_by(ProjectMember.sort_order.asc(), ProjectMember.id.asc())
            .first()
        )
        if member:
            return member.user_id
    return None


def _ensure_project_member(db: Session, project_id: int | None, user_id: int) -> None:
    if not project_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project is required")
    if not db.query(ProjectMember).filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Next handler is not a project member")


def _ensure_manual_owner_allowed(db: Session, project_id: int | None, user_id: int, rule: dict[str, Any]) -> None:
    _ensure_project_member(db, project_id, user_id)
    roles = _split_csv(rule.get("manual_owner_roles"))
    if not roles:
        return
    if not (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id, ProjectMember.project_role.in_(roles))
        .first()
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Next handler role is not allowed")


def _defer_requirement_links(db: Session, requirement: Requirement, payload: dict[str, Any], actor: User | None) -> None:
    target_iteration_id = payload.get("target_iteration_id") or payload.get("iteration_id")
    if target_iteration_id and requirement.iteration_id == target_iteration_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target iteration cannot be current iteration")
    if target_iteration_id:
        _ensure_iteration_scope(db, requirement.project_id, target_iteration_id)

    from_iteration_id = requirement.iteration_id
    requirement.iteration_id = target_iteration_id
    for task in db.query(Task).filter(Task.requirement_id == requirement.id, Task.deleted == 0).all():
        task.iteration_id = target_iteration_id
        if not is_terminal_state(task):
            definition = db.query(WorkflowDefinition).filter(WorkflowDefinition.id == task.workflow_definition_id).first()
            if definition and definition.initial_state_id:
                task.current_state_id = definition.initial_state_id
    for test_case in db.query(TestCase).filter(TestCase.requirement_id == requirement.id, TestCase.deleted == 0).all():
        test_case.iteration_id = target_iteration_id

    db.add(
        AuditLog(
            actor_id=actor.id if actor else None,
            action="defer",
            object_type="requirement",
            object_id=requirement.id,
            before_data={
                "iteration_id": from_iteration_id,
                "current_state_id": requirement.current_state_id,
                "status_name": requirement.status_name,
            },
            after_data={"iteration_id": target_iteration_id},
        )
    )


def _ensure_iteration_scope(db: Session, project_id: int | None, iteration_id: int) -> None:
    if not project_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project is required")
    iteration = db.query(Iteration).filter(Iteration.id == iteration_id, Iteration.deleted == 0).first()
    if not iteration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Iteration not found")
    if is_terminal_state(iteration):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Iteration is completed or canceled")
    scoped_project_ids = {row.project_id for row in db.query(IterationProject).filter(IterationProject.iteration_id == iteration_id).all()}
    if project_id not in scoped_project_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Iteration is not in project scope")


def _project_id_for_item(db: Session, object_type: str, item) -> int | None:
    if object_type == "project":
        return item.id
    if object_type == "iteration":
        row = db.query(IterationProject).filter(IterationProject.iteration_id == item.id).order_by(IterationProject.id.asc()).first()
        return row.project_id if row else None
    return getattr(item, "source_project_id", None) or getattr(item, "project_id", None)


def _object_type_for_item(item) -> str:
    for object_type, model in MODEL_BY_TYPE.items():
        if isinstance(item, model):
            return object_type
    raise KeyError(type(item))


def _owner_user(db: Session, owner_id: int | None) -> User | None:
    if not owner_id:
        return None
    return db.query(User).filter(User.id == owner_id).first()


def _last_bug_resolver_id(db: Session, item) -> int | None:
    if getattr(item, "resolved_by", None):
        return item.resolved_by
    operation = (
        db.query(StatusOperationLog)
        .filter(
            StatusOperationLog.object_type == "bug",
            StatusOperationLog.object_id == getattr(item, "id", None),
            StatusOperationLog.action == "resolve",
            StatusOperationLog.actor_id.isnot(None),
        )
        .order_by(StatusOperationLog.effective_time.desc(), StatusOperationLog.id.desc())
        .first()
    )
    return operation.actor_id if operation else None


def _split_csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _status_payload(request: WorkflowTransitionExecuteRequest) -> StatusOperationCreate:
    payload = request.payload or {}
    selected_values = _selected_values(request)
    return StatusOperationCreate(
        effective_time=_parse_effective_time(payload),
        reason=payload.get("reason"),
        remark=payload.get("remark"),
        target_iteration_id=payload.get("target_iteration_id") or payload.get("iteration_id"),
        delegate_reason=request.delegate_reason,
        selected_values=selected_values or None,
        default_target_status=payload.get("default_target_status"),
        resolved_target_status=payload.get("resolved_target_status"),
        override_reason=request.override_reason or payload.get("override_reason"),
    )


def _parse_effective_time(payload: dict[str, Any]):
    value = payload.get("effective_time")
    if not value or isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _append_remark(remark: str | None, addition: str) -> str:
    return f"{remark}; {addition}" if remark else addition
