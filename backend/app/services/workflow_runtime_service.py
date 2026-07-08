from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.bug import Bug
from app.models.iteration import Iteration, IterationProject
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.requirement import Requirement
from app.models.task import Task
from app.models.test_case import TestCase
from app.models.user import User
from app.models.workflow_definition import WorkflowDefinition, WorkflowTransition
from app.services.default_workflow_template_service import ensure_default_workflow_templates
from app.services.handler_transition_rule_service import _last_bug_resolver_id, _split_csv
from app.services.project_permission_service import can_admin_action, ensure_authenticated
from app.services.status_operation_service import create_status_operation
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

NORMALIZED_STATUS_SETS = {
    "requirement": {"pending_assignment", "in_processing", "pending_confirmation", "completed", "canceled"},
    "task": {"pending_assignment", "in_processing", "pending_confirmation", "completed", "canceled"},
    "bug": {"pending_handling", "fixing", "pending_verification", "verified", "closed"},
    "iteration": {"planning", "active", "completed", "canceled"},
    "project": {"planning", "active", "paused", "closed"},
}


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
    definition, from_status = definition_context
    transitions = (
        db.query(WorkflowTransition)
        .filter(
            WorkflowTransition.definition_id == definition.id,
            WorkflowTransition.from_status == from_status,
            WorkflowTransition.enabled == True,  # noqa: E712
        )
        .order_by(WorkflowTransition.sort_order.asc(), WorkflowTransition.id.asc())
        .all()
    )
    result = []
    for transition in transitions:
        if not _matches_transition_condition(item, transition):
            continue
        if not _can_see_transition(db, object_type, item, transition, actor):
            continue
        result.append(_transition_read(transition))
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
    transition, runtime_status = transition_context
    if runtime_status != item.status:
        item.status = runtime_status
    _ensure_can_execute(db, object_type, item, transition, actor, request)

    from_status = item.status
    delegated = _is_delegated(db, item, actor)
    delegated_owner = _owner_user(db, getattr(item, "owner_id", None)) if delegated else None
    original_owner_id = getattr(item, "owner_id", None)
    selected_values = _selected_values(request)
    default_target_status, resolved_target_status = _resolve_target_status(item, transition, request, selected_values)
    _apply_domain_payload(db, object_type, item, transition, request, actor, selected_values)
    _run_transition_validator(db, object_type, item, transition, resolved_target_status)
    item.status = resolved_target_status
    next_owner_id = _next_owner_id(db, object_type, item, transition, request, actor)
    if hasattr(item, "owner_id") and next_owner_id != original_owner_id:
        item.owner_id = next_owner_id
    next_owner = _owner_user(db, next_owner_id) if next_owner_id else None
    operation = create_status_operation(
        db,
        object_type=object_type,
        object_id=item.id,
        action=transition.action_key,
        from_status=from_status,
        to_status=resolved_target_status,
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
        operation.remark = _append_remark(operation.remark, f"handler transition to {next_owner_id}")
    db.commit()
    db.refresh(item)
    return WorkflowTransitionExecuteRead(
        object_type=object_type,
        id=item.id,
        status=item.status,
        owner_id=getattr(item, "owner_id", None),
        default_target_status=default_target_status,
        resolved_target_status=resolved_target_status,
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


def _workflow_definition_for_item(db: Session, object_type: str, item):
    resolved = _resolve_definition_context(db, object_type, item)
    return resolved[0] if resolved else None


def _definition_candidates_for_item(db: Session, object_type: str, item) -> list[WorkflowDefinition]:
    project_id = _project_id_for_item(db, object_type, item)
    project = db.query(Project).filter(Project.id == project_id, Project.deleted == 0).first() if project_id else None
    candidates: list[WorkflowDefinition] = []
    if project and project.assignee_rule_config_id:
        scoped_definition = (
            db.query(WorkflowDefinition)
            .filter(
                WorkflowDefinition.object_type == object_type,
                WorkflowDefinition.scope_type == "assignee_rule_config",
                WorkflowDefinition.scope_id == project.assignee_rule_config_id,
                WorkflowDefinition.enabled == True,  # noqa: E712
            )
            .order_by(WorkflowDefinition.id.desc())
            .first()
        )
        if scoped_definition:
            candidates.append(scoped_definition)
    default_definition = (
        db.query(WorkflowDefinition)
        .filter(
            WorkflowDefinition.object_type == object_type,
            WorkflowDefinition.scope_type == "system",
            WorkflowDefinition.is_default_template == True,  # noqa: E712
            WorkflowDefinition.enabled == True,  # noqa: E712
        )
        .order_by(WorkflowDefinition.id.desc())
        .first()
    )
    if default_definition:
        candidates.append(default_definition)
    return candidates


def _resolve_definition_context(db: Session, object_type: str, item) -> tuple[WorkflowDefinition, str] | None:
    for definition in _definition_candidates_for_item(db, object_type, item):
        for status_key in _status_candidates(object_type, item):
            transition_exists = (
                db.query(WorkflowTransition.id)
                .filter(
                    WorkflowTransition.definition_id == definition.id,
                    WorkflowTransition.from_status == status_key,
                    WorkflowTransition.enabled == True,  # noqa: E712
                )
                .first()
                is not None
            )
            if transition_exists:
                return definition, status_key
    return None


def _get_executable_transition(db: Session, object_type: str, item, action_key: str) -> tuple[WorkflowTransition, str]:
    for definition in _definition_candidates_for_item(db, object_type, item):
        for status_key in _status_candidates(object_type, item):
            transitions = (
                db.query(WorkflowTransition)
                .filter(
                    WorkflowTransition.definition_id == definition.id,
                    WorkflowTransition.from_status == status_key,
                    WorkflowTransition.action_key == action_key,
                    WorkflowTransition.enabled == True,  # noqa: E712
                )
                .order_by(WorkflowTransition.sort_order.asc(), WorkflowTransition.id.asc())
                .all()
            )
            for transition in transitions:
                if _matches_transition_condition(item, transition):
                    return transition, status_key
    if not _definition_candidates_for_item(db, object_type, item):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Workflow definition not found")
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Workflow transition not available")


def _transition_read(transition: WorkflowTransition) -> WorkflowTransitionActionRead:
    ui_config = transition.ui_config or {}
    form_config = dict(transition.form_config or {})
    handler_rule = transition.handler_rule or {}
    condition_config = transition.condition_config or {}
    routes = condition_config.get("routes") or {}
    if handler_rule.get("allow_manual_owner") and "allow_manual_owner" not in form_config:
        form_config["allow_manual_owner"] = True
    return WorkflowTransitionActionRead(
        action_key=transition.action_key,
        action_name=transition.action_name,
        from_status=transition.from_status,
        to_status=transition.to_status,
        button_type=ui_config.get("button_type", "primary"),
        list_display=ui_config.get("list_display", "more"),
        list_priority=int(ui_config.get("list_priority", transition.sort_order or 100)),
        requires_form=bool((form_config.get("fields") or [])),
        confirm_required=bool(ui_config.get("confirm_required", False)),
        routing_mode=condition_config.get("routing_mode"),
        allowed_target_statuses=sorted({str(value) for value in routes.values()}) if routes else [],
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
    if not _handler_allowed(db, object_type, item, actor):
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
    if not _handler_allowed(db, object_type, item, actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only current handler can execute transition")
    if delegated and not request.delegate_reason:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Please provide delegate reason")
    if not _role_allowed(db, object_type, item, transition, actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Transition role not allowed")


def _handler_allowed(db: Session, object_type: str, item, actor: User | None) -> bool:
    if not actor:
        return True
    owner_id = getattr(item, "owner_id", None)
    if owner_id:
        return owner_id == actor.id or _is_delegated(db, item, actor)
    if object_type in {"iteration", "project"}:
        return True
    return True


def _role_allowed(db: Session, object_type: str, item, transition: WorkflowTransition, actor: User | None) -> bool:
    roles = _split_csv(transition.allowed_roles)
    if not roles or not actor:
        return True
    project_id = _project_id_for_item(db, object_type, item)
    if not project_id:
        return True
    return bool(
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == actor.id, ProjectMember.project_role.in_(roles))
        .first()
    )


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


def _status_candidates(object_type: str, item) -> list[str]:
    status_key = getattr(item, "status", None)
    candidates: list[str] = []

    def _add(value: str | None) -> None:
        if value and value not in candidates:
            candidates.append(value)

    _add(status_key)
    owner_id = getattr(item, "owner_id", None)

    if object_type == "bug":
        if status_key in {"open", "reopened", "suspended"}:
            _add("pending_handling")
        elif status_key == "pending_handling":
            _add("open")
        elif status_key == "verifying":
            _add("pending_verification")
        elif status_key == "pending_verification":
            _add("verifying")
    elif object_type == "task":
        if status_key == "todo":
            _add("in_processing" if owner_id else "pending_assignment")
            _add("pending_assignment" if owner_id else "in_processing")
        elif status_key == "pending_assignment":
            _add("todo")
        elif status_key == "in_processing":
            _add("doing")
        elif status_key == "doing":
            _add("in_processing")
        elif status_key == "completed":
            _add("done")
        elif status_key == "done":
            _add("completed")
        elif status_key == "canceled":
            _add("closed")
        elif status_key == "closed":
            _add("canceled")
            _add("completed")
    elif object_type == "requirement":
        if status_key == "draft":
            _add("in_processing" if owner_id else "pending_assignment")
            _add("pending_assignment" if owner_id else "in_processing")
        elif status_key == "pending_assignment":
            _add("draft")
        elif status_key == "in_processing":
            _add("active")
        elif status_key == "active":
            _add("in_processing")
        elif status_key == "completed":
            _add("done")
        elif status_key == "done":
            _add("completed")
        elif status_key == "canceled":
            _add("closed")
        elif status_key == "closed":
            _add("canceled")
            _add("completed")
    elif object_type == "iteration":
        if status_key in {"draft", "open"}:
            _add("planning")
        elif status_key == "planning":
            _add("open")
        elif status_key in {"started", "doing"}:
            _add("active")
        elif status_key == "completed":
            _add("finished")
        elif status_key == "canceled":
            _add("closed")
        elif status_key in {"finished", "closed"}:
            _add("completed")
    elif object_type == "project":
        if status_key in {"draft", "open"}:
            _add("planning")
        elif status_key == "suspended":
            _add("paused")

    return candidates


def _normalized_status(object_type: str, item) -> str | None:
    candidates = _status_candidates(object_type, item)
    if not candidates:
        return getattr(item, "status", None)
    normalized_statuses = NORMALIZED_STATUS_SETS.get(object_type, set())
    for candidate in candidates:
        if candidate in normalized_statuses:
            return candidate
    return candidates[0]


def _resolve_target_status(item, transition: WorkflowTransition, request: WorkflowTransitionExecuteRequest, selected_values: dict[str, Any]) -> tuple[str, str]:
    default_target_status = transition.to_status
    resolved_target_status = transition.to_status
    condition_config = transition.condition_config or {}
    routes = condition_config.get("routes") or {}
    if routes:
        field_name = condition_config.get("field")
        selected_value = selected_values.get(field_name) if field_name else None
        if selected_value is None and field_name:
            selected_value = request.payload.get(field_name)
            if selected_value is not None:
                selected_values[field_name] = selected_value
        if field_name and selected_value is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field_name} is required")
        mapped_status = routes.get(selected_value)
        if not mapped_status:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Workflow routing configuration missing for selected value")
        default_target_status = mapped_status
        resolved_target_status = mapped_status
        selected_target_status = request.selected_target_status or request.payload.get("selected_target_status")
        if selected_target_status:
            allowed_statuses = set(routes.values())
            if selected_target_status not in allowed_statuses:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected target status is not allowed")
            resolved_target_status = selected_target_status
    return default_target_status, resolved_target_status


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


def _run_transition_validator(db: Session, object_type: str, item, transition: WorkflowTransition, resolved_target_status: str) -> None:
    validator = transition.validator_config or {}
    validator_type = validator.get("type")
    if not validator_type:
        return
    if validator_type == "bug_close_gate":
        _require_bug_close_tasks_complete(db, item, validator)
    elif validator_type == "requirement_terminal_gate":
        _require_requirement_relations_complete(db, item, resolved_target_status)
    elif validator_type == "iteration_terminal_gate":
        _require_iteration_items_complete(db, item.id)
    elif validator_type == "project_close_gate":
        _require_project_items_complete(db, item.id)


def _require_bug_close_tasks_complete(db: Session, bug: Bug, validator: dict[str, Any]) -> None:
    statuses = set(validator.get("direct_tasks_terminal_statuses") or ["completed", "canceled"])
    if not bug.task_id:
        return
    task = db.query(Task).filter(Task.id == bug.task_id, Task.deleted == 0).first()
    if task and _normalized_status("task", task) not in statuses:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bug cannot close while direct task is unfinished")


def _require_requirement_relations_complete(db: Session, requirement: Requirement, resolved_target_status: str) -> None:
    if resolved_target_status not in {"completed", "canceled"}:
        return
    blocking_tasks = [
        task
        for task in db.query(Task).filter(Task.requirement_id == requirement.id, Task.deleted == 0).all()
        if _normalized_status("task", task) not in {"completed", "canceled"}
    ]
    if blocking_tasks:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Requirement has unfinished task blockers")
    blocking_bugs = [
        bug
        for bug in db.query(Bug).filter(Bug.requirement_id == requirement.id, Bug.deleted == 0).all()
        if _normalized_status("bug", bug) != "closed"
    ]
    if blocking_bugs:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Requirement has unclosed bug blockers")


def _require_iteration_items_complete(db: Session, iteration_id: int) -> None:
    requirements = db.query(Requirement).filter(Requirement.iteration_id == iteration_id, Requirement.deleted == 0).all()
    blocking_messages: list[str] = []
    if any(_normalized_status("requirement", item) not in {"completed", "canceled"} for item in requirements):
        blocking_messages.append("requirement")
    tasks = db.query(Task).filter(Task.iteration_id == iteration_id, Task.deleted == 0).all()
    if any(_normalized_status("task", item) not in {"completed", "canceled"} for item in tasks):
        blocking_messages.append("task")
    bugs = db.query(Bug).filter(Bug.iteration_id == iteration_id, Bug.deleted == 0).all()
    if any(_normalized_status("bug", item) != "closed" for item in bugs):
        blocking_messages.append("bug")
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
    if any(_normalized_status("iteration", item) not in {"completed", "canceled"} for item in iterations):
        blocking_messages.append("iteration")
    requirements = db.query(Requirement).filter(Requirement.project_id == project_id, Requirement.deleted == 0).all()
    if any(_normalized_status("requirement", item) not in {"completed", "canceled"} for item in requirements):
        blocking_messages.append("requirement")
    tasks = db.query(Task).filter(Task.project_id == project_id, Task.deleted == 0).all()
    if any(_normalized_status("task", item) not in {"completed", "canceled"} for item in tasks):
        blocking_messages.append("task")
    bugs = db.query(Bug).filter(Bug.project_id == project_id, Bug.deleted == 0).all()
    if any(_normalized_status("bug", item) != "closed" for item in bugs):
        blocking_messages.append("bug")
    if blocking_messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Project has unfinished {', '.join(blocking_messages)} blockers",
        )


def _next_owner_id(
    db: Session,
    object_type: str,
    item,
    transition: WorkflowTransition,
    request: WorkflowTransitionExecuteRequest,
    actor: User | None,
) -> int | None:
    handler_rule = transition.handler_rule or {}
    if request.next_owner_id and handler_rule.get("allow_manual_owner"):
        _ensure_manual_owner_allowed(db, _project_id_for_item(db, object_type, item), request.next_owner_id, handler_rule)
        return request.next_owner_id
    original_owner_id = getattr(item, "owner_id", None)
    target = _resolve_owner(db, object_type, item, handler_rule, original_owner_id, actor, request)
    if target is None:
        target = _resolve_fallback_owner(db, object_type, item, handler_rule, original_owner_id)
    return target


def _resolve_owner(
    db: Session,
    object_type: str,
    item,
    rule: dict[str, Any],
    original_owner_id: int | None,
    actor: User | None,
    request: WorkflowTransitionExecuteRequest,
) -> int | None:
    target_type = rule.get("target_type", "keep_current")
    project_id = _project_id_for_item(db, object_type, item)
    if target_type == "keep_current":
        return original_owner_id
    if target_type == "none":
        return None
    if target_type == "actor":
        return actor.id if actor else original_owner_id
    if target_type == "explicit_owner":
        return request.next_owner_id or original_owner_id
    if target_type == "proposer":
        return getattr(item, "proposer_id", None)
    if target_type == "reporter":
        return getattr(item, "reporter_id", None)
    if target_type == "last_resolver" and object_type == "bug":
        return _last_bug_resolver_id(db, item)
    if target_type == "previous_handler":
        return original_owner_id
    if target_type == "project_role":
        return _first_project_member_id(db, project_id, _split_csv(rule.get("target_roles")))
    return original_owner_id


def _resolve_fallback_owner(db: Session, object_type: str, item, rule: dict[str, Any], original_owner_id: int | None) -> int | None:
    fallback_type = rule.get("fallback_type", "keep_current")
    project_id = _project_id_for_item(db, object_type, item)
    if fallback_type == "keep_current":
        return original_owner_id
    if fallback_type == "project_role":
        return _first_project_member_id(db, project_id, _split_csv(rule.get("fallback_roles")))
    return None


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
        if task.status != "canceled":
            task.status = "pending_assignment"
    for test_case in db.query(TestCase).filter(TestCase.requirement_id == requirement.id, TestCase.deleted == 0).all():
        test_case.iteration_id = target_iteration_id

    db.add(
        AuditLog(
            actor_id=actor.id if actor else None,
            action="defer",
            object_type="requirement",
            object_id=requirement.id,
            before_data={"iteration_id": from_iteration_id, "status": requirement.status},
            after_data={"iteration_id": target_iteration_id},
        )
    )


def _ensure_iteration_scope(db: Session, project_id: int | None, iteration_id: int) -> None:
    if not project_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project is required")
    iteration = db.query(Iteration).filter(Iteration.id == iteration_id, Iteration.deleted == 0).first()
    if not iteration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Iteration not found")
    if iteration.status in {"finished", "closed"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Iteration is finished or closed")
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
