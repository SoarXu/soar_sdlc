from collections import defaultdict
from copy import deepcopy
from datetime import datetime
from types import SimpleNamespace

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.assignee_rule_config import AssigneeRuleConfig
from app.models.project import Project
from app.models.role import Role
from app.models.workflow_definition import WorkflowDefinition, WorkflowState, WorkflowTransition, WorkflowTransitionRole
from app.services.role_capability_service import role_ids_for_capabilities
from app.services.default_workflow_template_service import ensure_default_workflow_templates, reconcile_review_subgraph
from app.views.assignee_rule_config_view import AssigneeRuleConfigCreate, AssigneeRuleConfigUpdate


DEFAULT_ASSIGNEE_RULE_CONFIG = {
    "name": "默认工作流规则",
    "description": "通过工作流和处理人流转规则分派当前处理人",
    "requirement_owner_role_ids": [],
    "task_owner_role_ids": [],
    "test_case_tester_role_ids": [],
    "test_run_owner_role_ids": [],
    "bug_owner_role_ids": [],
    "lifecycle_status": "enabled",
    "enabled": True,
}

SCHEME_WORKFLOW_OBJECT_TYPES = ("requirement", "task", "bug", "project")
SCHEME_WORKFLOW_LABELS = {
    "requirement": "需求",
    "task": "任务",
    "bug": "Bug",
    "project": "项目",
}
DEFAULT_SCHEME_WORKFLOW_OBJECT_TYPES = SCHEME_WORKFLOW_OBJECT_TYPES


def ensure_default_assignee_rule_config(db: Session) -> None:
    default_config = db.query(AssigneeRuleConfig).filter(
        AssigneeRuleConfig.name == DEFAULT_ASSIGNEE_RULE_CONFIG["name"]
    ).first()
    if default_config:
        _backfill_empty_default_workflows(db, default_config)
        db.commit()
        return

    legacy_default = db.query(AssigneeRuleConfig).filter(AssigneeRuleConfig.name == "默认责任人规则").first()
    if legacy_default:
        for field, value in DEFAULT_ASSIGNEE_RULE_CONFIG.items():
            setattr(legacy_default, field, value)
        default_config = legacy_default
    else:
        default_config = AssigneeRuleConfig(**DEFAULT_ASSIGNEE_RULE_CONFIG)
        db.add(default_config)
        db.flush()

    default_config.update_time = datetime.now()
    _backfill_empty_default_workflows(db, default_config)
    db.commit()


def _backfill_empty_default_workflows(db: Session, config: AssigneeRuleConfig) -> None:
    ensure_default_workflow_templates(db)
    source_definitions = _source_definitions(
        db,
        SimpleNamespace(source_type="system", source_id="system-standard"),
    )
    definitions_by_type = {
        item.object_type: item
        for item in db.query(WorkflowDefinition)
        .filter(
            WorkflowDefinition.scope_type == "assignee_rule_config",
            WorkflowDefinition.scope_id == config.id,
            WorkflowDefinition.object_type.in_(DEFAULT_SCHEME_WORKFLOW_OBJECT_TYPES),
            WorkflowDefinition.enabled.is_(True),
        )
        .order_by(WorkflowDefinition.id.asc())
        .all()
    }
    for object_type in DEFAULT_SCHEME_WORKFLOW_OBJECT_TYPES:
        definition = definitions_by_type.get(object_type)
        if definition is None:
            definition = WorkflowDefinition(
                name=f"{config.name}-{SCHEME_WORKFLOW_LABELS[object_type]}工作流",
                object_type=object_type,
                scope_type="assignee_rule_config",
                scope_id=config.id,
                template_key=None,
                parent_definition_id=None,
                is_default_template=False,
                enabled=True,
                version=1,
            )
            db.add(definition)
            db.flush()
        has_states = db.query(WorkflowState.id).filter(WorkflowState.definition_id == definition.id).first()
        has_transitions = db.query(WorkflowTransition.id).filter(
            WorkflowTransition.definition_id == definition.id
        ).first()
        if has_states or has_transitions:
            reconcile_review_subgraph(db, definition)
            continue
        _clone_graph(db, source_definitions[object_type], definition)
        reconcile_review_subgraph(db, definition)


def list_configs(db: Session) -> list[AssigneeRuleConfig]:
    ensure_default_assignee_rule_config(db)
    return db.query(AssigneeRuleConfig).order_by(AssigneeRuleConfig.lifecycle_status.asc(), AssigneeRuleConfig.id.asc()).all()


def list_project_options(db: Session) -> list[AssigneeRuleConfig]:
    ensure_default_assignee_rule_config(db)
    return (
        db.query(AssigneeRuleConfig)
        .filter(AssigneeRuleConfig.lifecycle_status == "enabled")
        .order_by(AssigneeRuleConfig.id.asc())
        .all()
    )


def default_project_workflow_scheme(db: Session) -> AssigneeRuleConfig:
    ensure_default_assignee_rule_config(db)
    config = db.query(AssigneeRuleConfig).filter(
        AssigneeRuleConfig.name == DEFAULT_ASSIGNEE_RULE_CONFIG["name"]
    ).first()
    if not config:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Default workflow scheme not found")
    if config.lifecycle_status != "enabled":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Default workflow scheme is not enabled")
    return config


def list_template_sources(db: Session) -> list[dict]:
    ensure_default_workflow_templates(db)
    sources = [
        {
            "source_type": "system",
            "source_id": "system-standard",
            "name": "系统标准方案",
            "description": "系统内置的项目、需求、任务和 Bug 标准工作流",
            "lifecycle_status": "enabled",
        }
    ]
    complete_scheme_ids = {
        item[0]
        for item in (
            db.query(WorkflowDefinition.scope_id)
            .filter(
                WorkflowDefinition.scope_type == "assignee_rule_config",
                WorkflowDefinition.object_type.in_(SCHEME_WORKFLOW_OBJECT_TYPES),
                WorkflowDefinition.enabled.is_(True),
            )
            .group_by(WorkflowDefinition.scope_id)
            .having(func.count(func.distinct(WorkflowDefinition.object_type)) == len(SCHEME_WORKFLOW_OBJECT_TYPES))
            .all()
        )
    }
    sources.extend(
        {
            "source_type": "scheme",
            "source_id": str(item.id),
            "name": item.name,
            "description": item.description,
            "lifecycle_status": item.lifecycle_status,
        }
        for item in (
            db.query(AssigneeRuleConfig)
            .filter(AssigneeRuleConfig.id.in_(complete_scheme_ids))
            .order_by(AssigneeRuleConfig.id.asc())
            .all()
        )
    )
    return sources


def create_config(db: Session, payload: AssigneeRuleConfigCreate) -> AssigneeRuleConfig:
    data = _clean_payload(payload.model_dump(exclude={"creation_mode", "template_source"}))
    _validate_role_ids(db, data)
    if "name" in data:
        if not data["name"]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name is required")
    if db.query(AssigneeRuleConfig).filter(AssigneeRuleConfig.name == data["name"]).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Config name already exists")
    if payload.creation_mode == "blank" and payload.template_source is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Blank creation does not accept a template source",
        )
    if payload.creation_mode == "template" and payload.template_source is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Template source is required",
        )
    if payload.template_source and payload.template_source.source_type == "system":
        if payload.template_source.source_id != "system-standard":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="System template source not found")
        ensure_default_workflow_templates(db)
    try:
        config = AssigneeRuleConfig(**data, lifecycle_status="draft", enabled=False)
        db.add(config)
        db.flush()
        for object_type in SCHEME_WORKFLOW_OBJECT_TYPES:
            db.add(
                WorkflowDefinition(
                    name=f"{config.name}-{SCHEME_WORKFLOW_LABELS[object_type]}工作流",
                    object_type=object_type,
                    scope_type="assignee_rule_config",
                    scope_id=config.id,
                    template_key=None,
                    parent_definition_id=None,
                    is_default_template=False,
                    enabled=True,
                    version=1,
                )
            )
        db.flush()
        if payload.creation_mode == "template":
            _copy_template_source(db, config.id, payload.template_source)
        db.commit()
        db.refresh(config)
        return config
    except Exception:
        db.rollback()
        raise


def clone_enabled_config(db: Session, source_config_id: int, name: str) -> AssigneeRuleConfig:
    source = (
        db.query(AssigneeRuleConfig)
        .filter(
            AssigneeRuleConfig.id == source_config_id,
            AssigneeRuleConfig.lifecycle_status == "enabled",
            AssigneeRuleConfig.enabled.is_(True),
        )
        .first()
    )
    if not source:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Source workflow scheme is not enabled")
    if db.query(AssigneeRuleConfig.id).filter(AssigneeRuleConfig.name == name).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Config name already exists")

    clone = AssigneeRuleConfig(
        name=name,
        description=source.description,
        requirement_owner_role_ids=list(source.requirement_owner_role_ids or []),
        task_owner_role_ids=list(source.task_owner_role_ids or []),
        test_case_tester_role_ids=list(source.test_case_tester_role_ids or []),
        test_run_owner_role_ids=list(source.test_run_owner_role_ids or []),
        bug_owner_role_ids=list(source.bug_owner_role_ids or []),
        lifecycle_status="enabled",
        enabled=True,
    )
    db.add(clone)
    db.flush()
    for object_type in SCHEME_WORKFLOW_OBJECT_TYPES:
        db.add(
            WorkflowDefinition(
                name=f"{clone.name}-{SCHEME_WORKFLOW_LABELS[object_type]}工作流",
                object_type=object_type,
                scope_type="assignee_rule_config",
                scope_id=clone.id,
                template_key=None,
                parent_definition_id=None,
                is_default_template=False,
                enabled=True,
                version=1,
            )
        )
    db.flush()
    _copy_template_source(
        db,
        clone.id,
        SimpleNamespace(source_type="scheme", source_id=str(source.id)),
    )
    invalid = _invalid_core_workflows(db, clone.id)
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Cloned workflow scheme is not runnable", "errors": invalid},
        )
    return clone


def _copy_template_source(db: Session, config_id: int, source) -> None:
    source_definitions = _source_definitions(db, source)
    target_definitions = {
        item.object_type: item
        for item in db.query(WorkflowDefinition)
        .filter(
            WorkflowDefinition.scope_type == "assignee_rule_config",
            WorkflowDefinition.scope_id == config_id,
        )
        .all()
    }
    for object_type in SCHEME_WORKFLOW_OBJECT_TYPES:
        _clone_graph(db, source_definitions[object_type], target_definitions[object_type])
    bug_definition = target_definitions["bug"]
    submit_verification = (
        db.query(WorkflowTransition)
        .filter(
            WorkflowTransition.definition_id == bug_definition.id,
            WorkflowTransition.action_key == "submit_verification",
        )
        .first()
    )
    if submit_verification:
        submit_verification.handler_rule = {
            **(submit_verification.handler_rule or {}),
            "target_type": "bug_verifier",
            "fallback_type": "project_role",
        }
        _replace_transition_role_purpose(
            db,
            submit_verification.id,
            "fallback",
            list(role_ids_for_capabilities(db, {"project_owner"})),
        )
    db.flush()



def _source_definitions(db: Session, source) -> dict[str, WorkflowDefinition]:
    if source.source_type == "system":
        if source.source_id != "system-standard":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="System template source not found")
        query = db.query(WorkflowDefinition).filter(
            WorkflowDefinition.scope_type == "system",
            WorkflowDefinition.is_default_template.is_(True),
            WorkflowDefinition.object_type.in_(SCHEME_WORKFLOW_OBJECT_TYPES),
        )
    else:
        try:
            source_config_id = int(source.source_id)
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid scheme source id") from exc
        source_config = db.query(AssigneeRuleConfig.id).filter(AssigneeRuleConfig.id == source_config_id).first()
        if not source_config:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow scheme source not found")
        query = db.query(WorkflowDefinition).filter(
            WorkflowDefinition.scope_type == "assignee_rule_config",
            WorkflowDefinition.scope_id == source_config_id,
            WorkflowDefinition.object_type.in_(SCHEME_WORKFLOW_OBJECT_TYPES),
            WorkflowDefinition.enabled.is_(True),
        )
    definitions: dict[str, WorkflowDefinition] = {}
    for item in query.order_by(WorkflowDefinition.id.desc()).all():
        definitions.setdefault(item.object_type, item)
    missing = set(SCHEME_WORKFLOW_OBJECT_TYPES) - set(definitions)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Template source is incomplete", "missing_object_types": sorted(missing)},
        )
    return definitions


def _clone_graph(db: Session, source: WorkflowDefinition, target: WorkflowDefinition) -> None:
    source_states = (
        db.query(WorkflowState)
        .filter(WorkflowState.definition_id == source.id)
        .order_by(WorkflowState.sort_order.asc(), WorkflowState.id.asc())
        .all()
    )
    state_id_map: dict[int, int] = {}
    for item in source_states:
        cloned = WorkflowState(
            definition_id=target.id,
            status_name=item.status_name,
            category=item.category,
            state_role=item.state_role,
            terminal_kind=item.terminal_kind,
            color=item.color,
            x=item.x,
            y=item.y,
            sort_order=item.sort_order,
            enabled=item.enabled,
        )
        db.add(cloned)
        db.flush()
        state_id_map[item.id] = cloned.id

    target.initial_state_id = state_id_map.get(source.initial_state_id)
    target.parent_definition_id = None
    source_transitions = (
        db.query(WorkflowTransition)
        .filter(WorkflowTransition.definition_id == source.id)
        .order_by(WorkflowTransition.sort_order.asc(), WorkflowTransition.id.asc())
        .all()
    )
    source_role_refs: dict[int, list[WorkflowTransitionRole]] = {}
    if source_transitions:
        for ref in db.query(WorkflowTransitionRole).filter(
            WorkflowTransitionRole.transition_id.in_([item.id for item in source_transitions])
        ).all():
            source_role_refs.setdefault(ref.transition_id, []).append(ref)
    for item in source_transitions:
        from_state_id = state_id_map[item.from_state_id]
        to_state_id = state_id_map[item.to_state_id]
        handler_rule = deepcopy(item.handler_rule)
        if source.object_type == "bug" and item.action_key == "submit_verification":
            handler_rule = {
                **(handler_rule or {}),
                "target_type": "bug_verifier",
                "fallback_type": "project_role",
            }
        cloned = WorkflowTransition(
                definition_id=target.id,
                action_key=item.action_key,
                action_name=item.action_name,
                from_state_id=from_state_id,
                to_state_id=to_state_id,
                allowed_roles=item.allowed_roles,
                handler_rule=handler_rule,
                trigger_config=deepcopy(item.trigger_config),
                condition_config=_remap_state_ids(item.condition_config, state_id_map),
                validator_config=deepcopy(item.validator_config),
                post_action_config=deepcopy(item.post_action_config),
                ui_config={key: value for key, value in (deepcopy(item.ui_config) or {}).items() if key != "system_action"},
                form_config=deepcopy(item.form_config),
                diagram_config=deepcopy(item.diagram_config),
                enabled=item.enabled,
                sort_order=item.sort_order,
            )
        db.add(cloned)
        db.flush()
        db.add_all(
            WorkflowTransitionRole(
                transition_id=cloned.id,
                role_id=ref.role_id,
                purpose=ref.purpose,
                sort_order=ref.sort_order,
            )
            for ref in source_role_refs.get(item.id, [])
        )
        if source.object_type == "bug" and item.action_key == "submit_verification":
            _replace_transition_role_purpose(
                db,
                cloned.id,
                "fallback",
                list(role_ids_for_capabilities(db, {"project_owner"})),
            )
    db.flush()


def synchronize_workflow_definition_graph(
    db: Session,
    source: WorkflowDefinition,
    target: WorkflowDefinition,
) -> None:
    if source.object_type != target.object_type:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Workflow object types do not match")
    source_states = (
        db.query(WorkflowState)
        .filter(WorkflowState.definition_id == source.id)
        .order_by(WorkflowState.sort_order.asc(), WorkflowState.id.asc())
        .all()
    )
    target_states = (
        db.query(WorkflowState)
        .filter(WorkflowState.definition_id == target.id)
        .order_by(WorkflowState.sort_order.asc(), WorkflowState.id.asc())
        .all()
    )
    state_matches = _match_workflow_states(source_states, target_states)
    state_id_map: dict[int, int] = {}
    matched_target_state_ids = set()
    for source_state in source_states:
        target_state = state_matches.get(source_state.id)
        if target_state is None:
            target_state = WorkflowState(definition_id=target.id)
            db.add(target_state)
        else:
            matched_target_state_ids.add(target_state.id)
        for field in (
            "status_name", "category", "state_role", "terminal_kind", "color", "x", "y", "sort_order", "enabled",
        ):
            setattr(target_state, field, getattr(source_state, field))
        db.flush()
        state_id_map[source_state.id] = target_state.id
    for target_state in target_states:
        if target_state.id not in matched_target_state_ids:
            target_state.enabled = False
    db.flush()
    source_transitions = (
        db.query(WorkflowTransition)
        .filter(WorkflowTransition.definition_id == source.id)
        .order_by(WorkflowTransition.sort_order.asc(), WorkflowTransition.id.asc())
        .all()
    )
    target_transitions = (
        db.query(WorkflowTransition)
        .filter(WorkflowTransition.definition_id == target.id)
        .order_by(WorkflowTransition.sort_order.asc(), WorkflowTransition.id.asc())
        .all()
    )
    transition_matches = _match_workflow_transitions(source_transitions, target_transitions, state_id_map)

    source_role_refs: dict[int, list[WorkflowTransitionRole]] = defaultdict(list)
    if source_transitions:
        for role_ref in (
            db.query(WorkflowTransitionRole)
            .filter(WorkflowTransitionRole.transition_id.in_([item.id for item in source_transitions]))
            .order_by(WorkflowTransitionRole.sort_order.asc(), WorkflowTransitionRole.id.asc())
            .all()
        ):
            source_role_refs[role_ref.transition_id].append(role_ref)
    matched_target_transition_ids = set()
    for source_transition in source_transitions:
        target_transition = transition_matches.get(source_transition.id)
        if target_transition is None:
            target_transition = WorkflowTransition(
                definition_id=target.id,
                action_key=source_transition.action_key,
                action_name=source_transition.action_name,
                from_state_id=state_id_map[source_transition.from_state_id],
                to_state_id=state_id_map[source_transition.to_state_id],
            )
            db.add(target_transition)
        else:
            matched_target_transition_ids.add(target_transition.id)
        for field in (
            "action_key", "action_name", "allowed_roles", "handler_rule", "trigger_config", "validator_config",
            "post_action_config", "ui_config", "form_config", "diagram_config", "enabled", "auto_disabled_by_state", "sort_order",
        ):
            setattr(target_transition, field, deepcopy(getattr(source_transition, field)))
        target_transition.from_state_id = state_id_map[source_transition.from_state_id]
        target_transition.to_state_id = state_id_map[source_transition.to_state_id]
        target_transition.condition_config = _remap_state_ids(source_transition.condition_config, state_id_map)
        db.flush()
        db.query(WorkflowTransitionRole).filter(
            WorkflowTransitionRole.transition_id == target_transition.id
        ).delete(synchronize_session=False)
        db.add_all(
            WorkflowTransitionRole(
                transition_id=target_transition.id,
                role_id=role_ref.role_id,
                purpose=role_ref.purpose,
                sort_order=role_ref.sort_order,
            )
            for role_ref in source_role_refs.get(source_transition.id, [])
        )
    for target_transition in target_transitions:
        if target_transition.id not in matched_target_transition_ids:
            target_transition.enabled = False
    target.initial_state_id = state_id_map.get(source.initial_state_id)
    target.version = (target.version or 1) + 1
    target.update_time = datetime.now()
    db.flush()


def synchronize_default_scheme_graphs_to_system_templates(db: Session) -> int:
    ensure_default_workflow_templates(db, reconcile_existing=False, commit=False)
    default_config = (
        db.query(AssigneeRuleConfig)
        .filter(AssigneeRuleConfig.name == DEFAULT_ASSIGNEE_RULE_CONFIG["name"])
        .first()
    )
    if default_config is None:
        return 0
    source_definitions = _workflow_definitions_by_type(
        db,
        db.query(WorkflowDefinition).filter(
            WorkflowDefinition.scope_type == "assignee_rule_config",
            WorkflowDefinition.scope_id == default_config.id,
            WorkflowDefinition.object_type.in_(SCHEME_WORKFLOW_OBJECT_TYPES),
            WorkflowDefinition.enabled.is_(True),
        ),
        "default workflow scheme",
    )
    target_definitions = _workflow_definitions_by_type(
        db,
        db.query(WorkflowDefinition).filter(
            WorkflowDefinition.scope_type == "system",
            WorkflowDefinition.is_default_template.is_(True),
            WorkflowDefinition.object_type.in_(SCHEME_WORKFLOW_OBJECT_TYPES),
            WorkflowDefinition.enabled.is_(True),
        ),
        "system workflow template",
    )
    for object_type in SCHEME_WORKFLOW_OBJECT_TYPES:
        synchronize_workflow_definition_graph(
            db,
            source_definitions[object_type],
            target_definitions[object_type],
        )
    return len(SCHEME_WORKFLOW_OBJECT_TYPES)


def _workflow_definitions_by_type(db: Session, query, label: str) -> dict[str, WorkflowDefinition]:
    definitions: dict[str, list[WorkflowDefinition]] = defaultdict(list)
    for definition in query.order_by(WorkflowDefinition.id.asc()).all():
        definitions[definition.object_type].append(definition)
    missing = set(SCHEME_WORKFLOW_OBJECT_TYPES) - set(definitions)
    duplicates = [object_type for object_type, items in definitions.items() if len(items) != 1]
    if missing or duplicates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{label} is incomplete or ambiguous",
        )
    return {object_type: definitions[object_type][0] for object_type in SCHEME_WORKFLOW_OBJECT_TYPES}


def _match_workflow_states(
    source_states: list[WorkflowState],
    target_states: list[WorkflowState],
) -> dict[int, WorkflowState]:
    matches: dict[int, WorkflowState] = {}
    unmatched_source = {item.id: item for item in source_states}
    unmatched_target = {item.id: item for item in target_states}
    _match_unique_state_groups(
        unmatched_source,
        unmatched_target,
        matches,
        lambda item: ("role", item.state_role) if item.state_role else None,
    )
    _match_unique_state_groups(
        unmatched_source,
        unmatched_target,
        matches,
        lambda item: ("name", item.status_name, item.category),
    )
    _match_unique_state_groups(
        unmatched_source,
        unmatched_target,
        matches,
        lambda item: ("shape", item.category, item.terminal_kind, item.sort_order),
    )
    return matches


def _match_unique_state_groups(unmatched_source, unmatched_target, matches, identity) -> None:
    source_groups: dict[tuple, list[WorkflowState]] = defaultdict(list)
    target_groups: dict[tuple, list[WorkflowState]] = defaultdict(list)
    for state in unmatched_source.values():
        key = identity(state)
        if key is not None:
            source_groups[key].append(state)
    for state in unmatched_target.values():
        key = identity(state)
        if key is not None:
            target_groups[key].append(state)
    for key, source_group in source_groups.items():
        target_group = target_groups.get(key, [])
        if len(source_group) == len(target_group) == 1:
            source_state, target_state = source_group[0], target_group[0]
            matches[source_state.id] = target_state
            unmatched_source.pop(source_state.id)
            unmatched_target.pop(target_state.id)


def _match_workflow_transitions(
    source_transitions: list[WorkflowTransition],
    target_transitions: list[WorkflowTransition],
    state_id_map: dict[int, int],
) -> dict[int, WorkflowTransition]:
    source_groups = _workflow_transition_groups(
        source_transitions,
        lambda item: (item.action_key, state_id_map[item.from_state_id]),
    )
    target_groups = _workflow_transition_groups(
        target_transitions,
        lambda item: (item.action_key, item.from_state_id),
    )
    matches: dict[int, WorkflowTransition] = {}
    for identity, source_group in source_groups.items():
        target_group = target_groups.get(identity, [])
        for source_transition, target_transition in _pair_transitions_by_target_state(
            source_group,
            target_group,
            state_id_map,
        ):
            matches[source_transition.id] = target_transition
    return matches


def _workflow_transition_groups(items, identity) -> dict[tuple, list[WorkflowTransition]]:
    grouped: dict[tuple, list[WorkflowTransition]] = defaultdict(list)
    for item in items:
        grouped[identity(item)].append(item)
    for group in grouped.values():
        group.sort(key=lambda item: (not item.enabled, item.sort_order, item.id))
    return dict(grouped)


def _pair_transitions_by_target_state(
    source_group: list[WorkflowTransition],
    target_group: list[WorkflowTransition],
    state_id_map: dict[int, int],
) -> list[tuple[WorkflowTransition, WorkflowTransition]]:
    target_by_state_id: dict[int, list[WorkflowTransition]] = defaultdict(list)
    for transition in target_group:
        target_by_state_id[transition.to_state_id].append(transition)
    matched_source_ids: set[int] = set()
    matched_target_ids: set[int] = set()
    matches = []
    for source_transition in source_group:
        target_transition = next(
            (
                item
                for item in target_by_state_id.get(state_id_map[source_transition.to_state_id], [])
                if item.id not in matched_target_ids
            ),
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


def _remap_state_ids(config, state_id_map: dict[int, int]):
    if not isinstance(config, dict):
        return deepcopy(config)
    remapped = deepcopy(config)
    for field in ("routes", "target_state_id_by_owner"):
        if isinstance(remapped.get(field), dict):
            remapped[field] = {
                key: state_id_map.get(value, value)
                for key, value in remapped[field].items()
            }
    return remapped


def _replace_transition_role_purpose(db: Session, transition_id: int, purpose: str, role_ids: list[int]) -> None:
    db.query(WorkflowTransitionRole).filter(
        WorkflowTransitionRole.transition_id == transition_id,
        WorkflowTransitionRole.purpose == purpose,
    ).delete()
    db.add_all(
        WorkflowTransitionRole(
            transition_id=transition_id,
            role_id=role_id,
            purpose=purpose,
            sort_order=index,
        )
        for index, role_id in enumerate(role_ids)
    )


def update_config(db: Session, config_id: int, payload: AssigneeRuleConfigUpdate) -> AssigneeRuleConfig:
    config = _get_config(db, config_id)
    data = _clean_payload(payload.model_dump(exclude_unset=True))
    _validate_role_ids(db, data)
    if "name" in data:
        if not data["name"]:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Name is required")
        existing = db.query(AssigneeRuleConfig).filter(AssigneeRuleConfig.name == data["name"]).first()
        if existing and existing.id != config_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Config name already exists")
    for field, value in data.items():
        setattr(config, field, value)
    config.update_time = datetime.now()
    db.commit()
    db.refresh(config)
    return config


def enable_config(db: Session, config_id: int) -> AssigneeRuleConfig:
    config = _get_config(db, config_id)
    if config.lifecycle_status == "disabled":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Disabled workflow scheme recovery is not supported",
        )
    invalid = _invalid_core_workflows(db, config_id)
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Workflow scheme is not runnable",
                "invalid_object_types": sorted(invalid),
                "errors": invalid,
            },
        )
    config.lifecycle_status = "enabled"
    config.enabled = True
    config.update_time = datetime.now()
    db.commit()
    db.refresh(config)
    return config


def disable_config(db: Session, config_id: int) -> AssigneeRuleConfig:
    config = _get_config(db, config_id)
    project_ids = [
        int(item[0])
        for item in db.query(Project.id)
        .filter(Project.assignee_rule_config_id == config_id, Project.deleted == 0)
        .order_by(Project.id.asc())
        .all()
    ]
    if project_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Workflow scheme is still assigned to projects",
                "project_count": len(project_ids),
                "project_ids": project_ids,
                "projects_url": f"/api/v1/projects?assignee_rule_config_id={config_id}",
            },
        )
    if config.lifecycle_status != "enabled":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only enabled workflow schemes can be disabled",
        )
    config.lifecycle_status = "disabled"
    config.enabled = False
    config.update_time = datetime.now()
    db.commit()
    db.refresh(config)
    return config


def _invalid_core_workflows(db: Session, config_id: int) -> dict[str, str]:
    invalid: dict[str, str] = {}
    for object_type in SCHEME_WORKFLOW_OBJECT_TYPES:
        definitions = (
            db.query(WorkflowDefinition)
            .filter(
                WorkflowDefinition.scope_type == "assignee_rule_config",
                WorkflowDefinition.scope_id == config_id,
                WorkflowDefinition.object_type == object_type,
                WorkflowDefinition.enabled.is_(True),
            )
            .all()
        )
        if len(definitions) != 1:
            invalid[object_type] = "exactly one enabled definition is required"
            continue
        definition = definitions[0]
        initial_state = (
            db.query(WorkflowState)
            .filter(
                WorkflowState.id == definition.initial_state_id,
                WorkflowState.definition_id == definition.id,
                WorkflowState.enabled.is_(True),
            )
            .first()
        )
        if not initial_state:
            invalid[object_type] = "an enabled initial state is required"
            continue
        enabled_state_ids = {
            int(item[0])
            for item in db.query(WorkflowState.id)
            .filter(WorkflowState.definition_id == definition.id, WorkflowState.enabled.is_(True))
            .all()
        }
        transitions = (
            db.query(WorkflowTransition)
            .filter(WorkflowTransition.definition_id == definition.id, WorkflowTransition.enabled.is_(True))
            .all()
        )
        if not transitions:
            invalid[object_type] = "at least one enabled transition is required"
            continue
        if any(
            item.from_state_id not in enabled_state_ids or item.to_state_id not in enabled_state_ids
            for item in transitions
        ):
            invalid[object_type] = "all transitions must reference enabled states in the definition"
    return invalid


def _get_config(db: Session, config_id: int) -> AssigneeRuleConfig:
    config = db.query(AssigneeRuleConfig).filter(AssigneeRuleConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignee rule config not found")
    return config


def _clean_payload(data: dict) -> dict:
    cleaned = dict(data)
    if "name" in cleaned and cleaned["name"] is not None:
        cleaned["name"] = cleaned["name"].strip()
    for field in [
        "requirement_owner_role_ids",
        "task_owner_role_ids",
        "test_case_tester_role_ids",
        "test_run_owner_role_ids",
        "bug_owner_role_ids",
    ]:
        if field in cleaned and cleaned[field] is not None:
            cleaned[field] = _normalize_role_ids(cleaned[field])
    return cleaned


def _normalize_role_ids(value) -> list[int]:
    if not isinstance(value, list) or any(isinstance(item, bool) or not isinstance(item, int) or item <= 0 for item in value):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="角色 ID 必须为正整数数组")
    if len(set(value)) != len(value):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="角色 ID 不能重复")
    return list(value)


def _validate_role_ids(db: Session, data: dict) -> None:
    submitted = {
        role_id
        for field, values in data.items()
        if field.endswith("_role_ids") and values is not None
        for role_id in values
    }
    if not submitted:
        return
    persisted = {
        role_id
        for (role_id,) in db.query(Role.id).filter(Role.id.in_(submitted), Role.enabled.is_(True)).all()
    }
    if submitted - persisted:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="所选角色不存在或已停用")
