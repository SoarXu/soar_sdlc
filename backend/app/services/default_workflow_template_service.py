from sqlalchemy.orm import Session

from app.models.role import RoleCapability
from app.models.workflow_definition import WorkflowDefinition, WorkflowState, WorkflowTransition, WorkflowTransitionRole
from app.views.workflow_definition_view import (
    WorkflowTemplateGraph as WorkflowGraphSave,
    WorkflowTemplateState as WorkflowStateBase,
    WorkflowTemplateTransition as WorkflowTransitionBase,
)


WORK_ITEM_STATE_MATRIX_OBJECT_TYPES = {"requirement", "task", "bug"}
ASSIGNMENT_TARGET_STATE_ROLES = {
    "active": "active_work",
    "inactive": "waiting_iteration",
}


def ensure_default_workflow_templates(db: Session) -> list[WorkflowDefinition]:
    definitions: list[WorkflowDefinition] = []
    for spec in _default_template_specs():
        definition = (
            db.query(WorkflowDefinition)
            .filter(
                WorkflowDefinition.scope_type == "system",
                WorkflowDefinition.object_type == spec["object_type"],
                WorkflowDefinition.template_key == spec["template_key"],
            )
            .first()
        )
        if not definition:
            definition = WorkflowDefinition(
                name=spec["name"],
                object_type=spec["object_type"],
                scope_type="system",
                scope_id=None,
                template_key=spec["template_key"],
                parent_definition_id=None,
                is_default_template=True,
                enabled=True,
                version=1,
            )
            db.add(definition)
            db.flush()
            _create_graph(db, definition, spec["graph"])
        else:
            reconcile_review_subgraph(db, definition)
            reconcile_work_item_state_matrix(db, definition)
        definitions.append(definition)
    configured_workflows = (
        db.query(WorkflowDefinition)
        .filter(WorkflowDefinition.object_type.in_(WORK_ITEM_STATE_MATRIX_OBJECT_TYPES))
        .all()
    )
    for definition in configured_workflows:
        if definition not in definitions:
            reconcile_work_item_state_matrix(db, definition)
    reconcile_managed_bug_action_matrices(db)
    reconcile_managed_task_terminal_gates(db)
    db.commit()
    for definition in definitions:
        db.refresh(definition)
    return definitions


def graph_for_object_type(object_type: str) -> WorkflowGraphSave:
    for spec in _default_template_specs():
        if spec["object_type"] == object_type:
            return spec["graph"]
    raise KeyError(object_type)


def default_template_summaries() -> list[dict]:
    return [
        {
            "template_key": spec["template_key"],
            "template_name": spec["name"],
            "target_object": spec["object_type"],
            "trigger_action": "status_transition",
            "description": spec["description"],
            "condition_json": {},
            "action_json": {
                "states": [state.model_dump() for state in spec["graph"].states],
                "transitions": [transition.model_dump() for transition in spec["graph"].transitions],
            },
        }
        for spec in _default_template_specs()
    ]


def _create_graph(db: Session, definition: WorkflowDefinition, graph: WorkflowGraphSave) -> None:
    state_by_ref: dict[str, WorkflowState] = {}
    for item in graph.states:
        data = item.model_dump(exclude={"ref"})
        state = WorkflowState(
            definition_id=definition.id,
            **data,
        )
        db.add(state)
        db.flush()
        state_by_ref[item.ref] = state

    for item in graph.transitions:
        from_state = state_by_ref[item.from_ref]
        to_state = state_by_ref[item.to_ref]
        condition_config = _template_condition_config(item.condition_config, state_by_ref)
        data = item.model_dump(exclude={"from_ref", "to_ref", "condition_config"})
        data.update(
            {
                "from_state_id": from_state.id,
                "to_state_id": to_state.id,
                "condition_config": condition_config,
            }
        )
        role_refs = _template_role_refs(db, data)
        transition = WorkflowTransition(definition_id=definition.id, **data)
        db.add(transition)
        db.flush()
        _replace_transition_role_refs(db, transition.id, role_refs)

    initial = next((item for item in graph.states if item.category == "start" and item.enabled), None)
    definition.initial_state_id = state_by_ref[initial.ref].id if initial else None


def _template_role_refs(db: Session, data: dict) -> dict[str, list[int]]:
    identities, allowed_role_ids = _template_role_values(db, data.get("allowed_roles"))
    data["allowed_roles"] = ",".join(identities)
    handler_rule = dict(data.get("handler_rule") or {})
    _identities, target_role_ids = _template_role_values(db, handler_rule.pop("target_roles", ""))
    _identities, fallback_role_ids = _template_role_values(db, handler_rule.pop("fallback_roles", ""))
    data["handler_rule"] = handler_rule or None
    condition = data.get("condition_config")
    if isinstance(condition, dict) and "allow_override_roles" in condition:
        condition = dict(condition)
        _identities, override_role_ids = _template_role_values(db, condition.pop("allow_override_roles"))
        condition["allow_override_role_ids"] = override_role_ids
        data["condition_config"] = condition
    return {
        "allowed": allowed_role_ids,
        "target": target_role_ids,
        "fallback": fallback_role_ids,
    }


def _template_role_values(db: Session, value) -> tuple[list[str], list[int]]:
    identities: list[str] = []
    role_ids: list[int] = []
    aliases = {
        "product_owner": ("product_owner", "product_manager"),
        "tech_lead": ("tech_lead", "development_lead"),
        "test_lead": ("test_lead", "tester"),
    }
    identity_values = {"system_admin", "project_member", "current_handler", "owner", "creator", "reporter", "proposer"}
    values = value if isinstance(value, list) else str(value or "").split(",")
    for raw_value in values:
        name = str(raw_value).strip()
        if not name:
            continue
        if name in identity_values:
            identities.append(name)
            continue
        role_id = None
        for capability in aliases.get(name, (name,)):
            role_id = db.query(RoleCapability.role_id).filter(RoleCapability.capability == capability).scalar()
            if role_id is not None:
                break
        if role_id is None:
            raise RuntimeError(f"Default workflow role is not configured: {name}")
        role_ids.append(int(role_id))
    return list(dict.fromkeys(identities)), list(dict.fromkeys(role_ids))


def _replace_transition_role_refs(db: Session, transition_id: int, role_refs: dict[str, list[int]]) -> None:
    db.query(WorkflowTransitionRole).filter(WorkflowTransitionRole.transition_id == transition_id).delete()
    for purpose, role_ids in role_refs.items():
        db.add_all(
            WorkflowTransitionRole(
                transition_id=transition_id,
                role_id=role_id,
                purpose=purpose,
                sort_order=index,
            )
        for index, role_id in enumerate(role_ids)
    )


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


def reconcile_review_subgraph(db: Session, definition: WorkflowDefinition) -> None:
    """Append the Git review gate to a recognized default graph without replacing it."""
    specification = {
        "requirement": ("complete", "in_processing", "completed"),
        "task": ("submit_confirmation", "in_processing", "pending_confirmation"),
        "bug": ("submit_verification", "fixing", "pending_verification"),
    }.get(definition.object_type)
    if not specification:
        return
    successor_action, development_ref, successor_ref = specification
    transitions = db.query(WorkflowTransition).filter(WorkflowTransition.definition_id == definition.id).all()
    states = {state.id: state for state in db.query(WorkflowState).filter(WorkflowState.definition_id == definition.id).all()}
    by_action = {transition.action_key: transition for transition in transitions}
    existing_successor = by_action.get(successor_action)
    if not existing_successor:
        return
    development_state = states.get(existing_successor.from_state_id)
    successor_state = states.get(existing_successor.to_state_id)
    if not development_state or not successor_state:
        return
    if definition.object_type == "bug" and existing_successor.handler_rule.get("target_type") != "bug_verifier":
        existing_successor.handler_rule = {
            **(existing_successor.handler_rule or {}),
            "target_type": "bug_verifier",
            "fallback_type": "project_role",
        }
        _replace_transition_role_purpose(
            db,
            existing_successor.id,
            "fallback",
            _template_role_values(db, "project_owner")[1],
        )
    review_state = next((state for state in states.values() if state.status_name == "待评审"), None)
    if review_state is None:
        review_state = WorkflowState(
            definition_id=definition.id,
            status_name="待评审",
            category="normal",
            color="#d97706",
            x=development_state.x + 180,
            y=development_state.y + 120,
            sort_order=max((state.sort_order for state in states.values()), default=0) + 1,
            enabled=True,
        )
        db.add(review_state)
        db.flush()
    transitions_by_key = {transition.action_key: transition for transition in transitions}
    review_transition_specs = (
        ("submit_review", "提交评审", development_state.id, review_state.id, "current_handler"),
        ("approve_review", "评审通过", review_state.id, successor_state.id, "development_lead"),
        ("reject_review", "评审驳回", review_state.id, development_state.id, "development_lead"),
    )
    for action_key, action_name, from_state_id, to_state_id, allowed_roles in review_transition_specs:
        transition = transitions_by_key.get(action_key)
        if transition:
            if action_key == "submit_review":
                transition.trigger_config = None
                transition.ui_config = {key: value for key, value in (transition.ui_config or {}).items() if key != "system_action"}
            continue
        transition = WorkflowTransition(
                definition_id=definition.id,
                action_key=action_key,
                action_name=action_name,
                from_state_id=from_state_id,
                to_state_id=to_state_id,
                allowed_roles="",
                handler_rule={"target_type": "keep_current"},
                trigger_config=None,
                ui_config={
                    "action_category": "process",
                    "list_display": "primary",
                    "list_priority": 10,
                    "handler_scope": "allowed_identity",
                },
                enabled=True,
                sort_order=max((item.sort_order for item in transitions), default=0) + 1,
            )
        db.add(transition)
        db.flush()
        identities, role_ids = _template_role_values(db, allowed_roles)
        transition.allowed_roles = ",".join(identities)
        _replace_transition_role_refs(db, transition.id, {"allowed": role_ids})


def reconcile_work_item_state_matrix(db: Session, definition: WorkflowDefinition) -> bool:
    """Upgrade a recognized pre-matrix graph without depending on display names."""
    if definition.object_type not in WORK_ITEM_STATE_MATRIX_OBJECT_TYPES:
        return False
    states = (
        db.query(WorkflowState)
        .filter(WorkflowState.definition_id == definition.id)
        .order_by(WorkflowState.id.asc())
        .all()
    )
    transitions = (
        db.query(WorkflowTransition)
        .filter(WorkflowTransition.definition_id == definition.id)
        .order_by(WorkflowTransition.id.asc())
        .all()
    )
    states_by_id = {state.id: state for state in states}
    states_by_role = {state.state_role: state for state in states if state.state_role}
    unassigned = states_by_role.get("unassigned")
    active = states_by_role.get("active_work")
    assignment_transitions = [
        transition
        for transition in transitions
        if transition.action_key in {"claim", "assign"}
    ]

    if unassigned is None:
        source_ids = {transition.from_state_id for transition in assignment_transitions}
        if len(source_ids) != 1:
            return False
        unassigned = states_by_id.get(source_ids.pop())
    if active is None:
        active_ids = {
            transition.to_state_id
            for transition in assignment_transitions
            if transition.to_state_id != unassigned.id
        }
        if definition.object_type == "bug" and not active_ids:
            active_ids = {
                transition.to_state_id
                for transition in transitions
                if transition.action_key == "confirm_bug_type"
                and transition.from_state_id == unassigned.id
            }
        if len(active_ids) != 1:
            return False
        active = states_by_id.get(active_ids.pop())
    if not unassigned or not active or unassigned.id == active.id:
        return False

    changed = False
    for state, role in ((unassigned, "unassigned"), (active, "active_work")):
        if state.state_role not in {None, role}:
            return False
        if state.state_role != role:
            state.state_role = role
            changed = True
    if (
        definition.object_type == "bug"
        and definition.template_key == "bug.default"
        and unassigned.status_name != "待分派"
    ):
        unassigned.status_name = "待分派"
        changed = True

    waiting = states_by_role.get("waiting_iteration")
    if waiting is None:
        waiting = WorkflowState(
            definition_id=definition.id,
            status_name="待开始",
            category="normal",
            state_role="waiting_iteration",
            color="#7c3aed",
            x=(unassigned.x + active.x) // 2,
            y=(unassigned.y + active.y) // 2,
            sort_order=max((state.sort_order for state in states), default=0) + 1,
            enabled=True,
        )
        db.add(waiting)
        db.flush()
        states.append(waiting)
        states_by_id[waiting.id] = waiting
        changed = True

    assignment_transitions = [
        transition
        for transition in transitions
        if transition.action_key in {"claim", "assign"}
        and transition.from_state_id == unassigned.id
    ]
    if not assignment_transitions:
        return False
    for transition in assignment_transitions:
        if transition.to_state_id != waiting.id:
            transition.to_state_id = waiting.id
            changed = True
        condition_config = dict(transition.condition_config or {})
        if condition_config.get("target_state_role_by_iteration_phase") != ASSIGNMENT_TARGET_STATE_ROLES:
            condition_config["target_state_role_by_iteration_phase"] = dict(ASSIGNMENT_TARGET_STATE_ROLES)
            transition.condition_config = condition_config
            changed = True

    transitions_by_identity = {
        (transition.action_key, transition.from_state_id, transition.to_state_id): transition
        for transition in transitions
    }
    start_key = ("start_iteration", waiting.id, active.id)
    if start_key not in transitions_by_identity:
        transition = WorkflowTransition(
            definition_id=definition.id,
            action_key="start_iteration",
            action_name="迭代启动",
            from_state_id=waiting.id,
            to_state_id=active.id,
            allowed_roles="",
            handler_rule={"target_type": "keep_current"},
            trigger_config={"type": "system_action"},
            ui_config={"action_category": "process", "list_display": "more"},
            enabled=True,
            sort_order=max((item.sort_order for item in transitions), default=0) + 1,
        )
        db.add(transition)
        db.flush()
        transitions.append(transition)
        changed = True

    for source in (waiting, active):
        key = ("unassign", source.id, unassigned.id)
        existing = transitions_by_identity.get(key)
        if existing:
            handler_rule = dict(existing.handler_rule or {})
            if handler_rule.get("target_type") != "none" or handler_rule.get("fallback_type") != "none":
                existing.handler_rule = {**handler_rule, "target_type": "none", "fallback_type": "none"}
                changed = True
            continue
        transition = WorkflowTransition(
            definition_id=definition.id,
            action_key="unassign",
            action_name="取消指派",
            from_state_id=source.id,
            to_state_id=unassigned.id,
            allowed_roles="current_handler,project_owner",
            handler_rule={"target_type": "none", "fallback_type": "none"},
            ui_config={
                "action_category": "management",
                "list_display": "more",
                "handler_scope": "allowed_identity",
                "requires_owner": True,
            },
            enabled=True,
            sort_order=max((item.sort_order for item in transitions), default=0) + 1,
        )
        db.add(transition)
        db.flush()
        transitions.append(transition)
        transitions_by_identity[key] = transition
        changed = True

    if changed:
        definition.version = (definition.version or 1) + 1
    return changed


def reconcile_managed_bug_action_matrices(db: Session) -> int:
    """Align only system or provably system-derived Bug workflows."""
    definitions = (
        db.query(WorkflowDefinition)
        .filter(WorkflowDefinition.object_type == "bug")
        .order_by(WorkflowDefinition.id.asc())
        .all()
    )
    return sum(
        1
        for definition in definitions
        if _is_managed_bug_workflow(db, definition)
        and reconcile_bug_action_matrix(db, definition)
    )


def reconcile_managed_task_terminal_gates(db: Session) -> int:
    definitions = (
        db.query(WorkflowDefinition)
        .filter(WorkflowDefinition.object_type == "task")
        .order_by(WorkflowDefinition.id.asc())
        .all()
    )
    return sum(
        reconcile_task_terminal_gates(db, definition)
        for definition in definitions
        if _is_managed_task_workflow(db, definition)
    )


def reconcile_task_terminal_gates(db: Session, definition: WorkflowDefinition) -> bool:
    terminal_state_ids = {
        state_id
        for (state_id,) in db.query(WorkflowState.id)
        .filter(
            WorkflowState.definition_id == definition.id,
            WorkflowState.category == "terminal",
            WorkflowState.enabled.is_(True),
        )
        .all()
    }
    if not terminal_state_ids:
        return False
    changed = False
    transitions = (
        db.query(WorkflowTransition)
        .filter(
            WorkflowTransition.definition_id == definition.id,
            WorkflowTransition.to_state_id.in_(terminal_state_ids),
            WorkflowTransition.from_state_id != WorkflowTransition.to_state_id,
            WorkflowTransition.enabled.is_(True),
        )
        .order_by(WorkflowTransition.id.asc())
        .all()
    )
    for transition in transitions:
        validators = transition.validator_config if isinstance(transition.validator_config, list) else [transition.validator_config]
        validators = [validator for validator in validators if validator]
        if any(validator.get("type") == "task_descendants_terminal_gate" for validator in validators):
            continue
        validators.append({"type": "task_descendants_terminal_gate"})
        transition.validator_config = validators[0] if len(validators) == 1 else validators
        changed = True
    if changed:
        definition.version = (definition.version or 1) + 1
    return changed


def _is_managed_task_workflow(db: Session, definition: WorkflowDefinition) -> bool:
    if (
        definition.scope_type == "system"
        and definition.template_key == "task.default"
        and definition.is_default_template
    ):
        return True
    if definition.parent_definition_id:
        parent = db.query(WorkflowDefinition).filter(
            WorkflowDefinition.id == definition.parent_definition_id
        ).first()
        return bool(
            parent
            and parent.scope_type == "system"
            and parent.template_key == "task.default"
            and parent.is_default_template
            and _matches_legacy_default_task_fingerprint(db, definition)
        )
    return _matches_legacy_default_task_fingerprint(db, definition)


def _matches_legacy_default_task_fingerprint(db: Session, definition: WorkflowDefinition) -> bool:
    if definition.scope_type != "assignee_rule_config":
        return False
    state_roles = {
        state_role
        for (state_role,) in db.query(WorkflowState.state_role)
        .filter(WorkflowState.definition_id == definition.id)
        .all()
        if state_role
    }
    if not {"unassigned", "waiting_iteration", "active_work"} <= state_roles:
        return False
    action_keys = {
        action_key
        for (action_key,) in db.query(WorkflowTransition.action_key)
        .filter(WorkflowTransition.definition_id == definition.id)
        .all()
    }
    return {
        "claim",
        "assign",
        "start_iteration",
        "unassign",
        "complete",
        "submit_confirmation",
        "approve_confirmation",
        "return_rework",
        "cancel",
        "reactivate",
    } <= action_keys


def reconcile_bug_action_matrix(db: Session, definition: WorkflowDefinition) -> bool:
    """Reconcile the N-004 action matrix using stable N-002 state roles only."""
    if definition.object_type != "bug":
        return False
    states_by_role = {
        state.state_role: state
        for state in db.query(WorkflowState)
        .filter(WorkflowState.definition_id == definition.id)
        .all()
        if state.state_role
    }
    required_roles = ("unassigned", "waiting_iteration", "active_work")
    missing_roles = [role for role in required_roles if role not in states_by_role]
    if missing_roles:
        raise RuntimeError(
            f"Bug workflow {definition.id} is missing N-002 state roles: {', '.join(missing_roles)}"
        )

    unassigned = states_by_role["unassigned"]
    waiting = states_by_role["waiting_iteration"]
    active = states_by_role["active_work"]
    transitions = (
        db.query(WorkflowTransition)
        .filter(WorkflowTransition.definition_id == definition.id)
        .order_by(WorkflowTransition.id.asc())
        .all()
    )
    changed = False
    for transition in transitions:
        if (
            transition.from_state_id == unassigned.id
            and transition.action_key in {"transfer", "change_handler"}
            and transition.enabled
        ):
            transition.enabled = False
            changed = True
        if (
            transition.from_state_id == active.id
            and transition.action_key == "edit"
            and transition.enabled
        ):
            transition.enabled = False
            changed = True

    has_active_confirmation = any(
        transition.from_state_id == active.id and transition.action_key == "confirm_bug_type"
        for transition in transitions
    )
    confirmation_changed = _move_bug_confirmation_to_active_state(
        db, definition, unassigned, active
    )
    changed = confirmation_changed or changed
    if confirmation_changed or not has_active_confirmation:
        changed = _upsert_bug_matrix_transition(
            db, definition, _bug_confirmation_transition(), active
        ) or changed

    for template, source in (
        (_command_transition("edit", "编辑", "pending_handling", allowed_roles="creator", command_type="edit"), unassigned),
        (_ownership_transition("transfer", "转派", "waiting_iteration"), waiting),
        (_ownership_transition("change_handler", "变更处理人", "waiting_iteration", management=True), waiting),
        (_command_transition("edit", "编辑", "waiting_iteration", allowed_roles="creator", command_type="edit"), waiting),
        (_ownership_transition("transfer", "转派", "fixing"), active),
        (_ownership_transition("change_handler", "变更处理人", "fixing", management=True), active),
    ):
        changed = _upsert_bug_matrix_transition(db, definition, template, source) or changed

    if changed:
        definition.version = (definition.version or 1) + 1
    return changed


def _move_bug_confirmation_to_active_state(
    db: Session,
    definition: WorkflowDefinition,
    unassigned: WorkflowState,
    active: WorkflowState,
) -> bool:
    transitions = (
        db.query(WorkflowTransition)
        .filter(
            WorkflowTransition.definition_id == definition.id,
            WorkflowTransition.action_key == "confirm_bug_type",
        )
        .order_by(WorkflowTransition.id.asc())
        .all()
    )
    active_transition = next(
        (transition for transition in transitions if transition.from_state_id == active.id),
        None,
    )
    changed = False
    if active_transition is None:
        legacy_transition = next(
            (transition for transition in transitions if transition.from_state_id == unassigned.id),
            None,
        )
        if legacy_transition is not None:
            legacy_transition.from_state_id = active.id
            legacy_transition.to_state_id = active.id
            active_transition = legacy_transition
            changed = True
    for transition in transitions:
        if transition is active_transition or transition.from_state_id == active.id:
            continue
        if transition.enabled:
            transition.enabled = False
            changed = True
    return changed


def _is_managed_bug_workflow(db: Session, definition: WorkflowDefinition) -> bool:
    if (
        definition.scope_type == "system"
        and definition.template_key == "bug.default"
        and definition.is_default_template
    ):
        return True
    if definition.parent_definition_id:
        parent = db.query(WorkflowDefinition).filter(
            WorkflowDefinition.id == definition.parent_definition_id
        ).first()
        return bool(
            parent
            and parent.scope_type == "system"
            and parent.template_key == "bug.default"
            and parent.is_default_template
            and _matches_legacy_default_bug_fingerprint(db, definition)
            and {"unassigned", "waiting_iteration", "active_work"}
            <= {
                state_role
                for (state_role,) in db.query(WorkflowState.state_role)
                .filter(WorkflowState.definition_id == definition.id)
                .all()
                if state_role
            }
        )
    return _matches_legacy_default_bug_fingerprint(db, definition)


def _matches_legacy_default_bug_fingerprint(db: Session, definition: WorkflowDefinition) -> bool:
    if definition.scope_type != "assignee_rule_config":
        return False
    states_by_role = {
        state.state_role: state
        for state in db.query(WorkflowState)
        .filter(WorkflowState.definition_id == definition.id)
        .all()
        if state.state_role
    }
    required_roles = {"unassigned", "waiting_iteration", "active_work"}
    if not required_roles <= set(states_by_role):
        return False
    action_keys_by_role = {
        role: {
            action_key
            for (action_key,) in db.query(WorkflowTransition.action_key)
            .filter(
                WorkflowTransition.definition_id == definition.id,
                WorkflowTransition.from_state_id == state.id,
            )
            .all()
        }
        for role, state in states_by_role.items()
    }
    return (
        {"claim", "assign", "transfer", "change_handler"} <= action_keys_by_role["unassigned"]
        and {"start_iteration", "unassign"} <= action_keys_by_role["waiting_iteration"]
        and {"transfer", "change_handler", "unassign"} <= action_keys_by_role["active_work"]
    )


def _upsert_bug_matrix_transition(
    db: Session,
    definition: WorkflowDefinition,
    template: WorkflowTransitionBase,
    source: WorkflowState,
) -> bool:
    transition = (
        db.query(WorkflowTransition)
        .filter(
            WorkflowTransition.definition_id == definition.id,
            WorkflowTransition.from_state_id == source.id,
            WorkflowTransition.action_key == template.action_key,
        )
        .order_by(WorkflowTransition.id.asc())
        .first()
    )
    data = template.model_dump(exclude={"from_ref", "to_ref"})
    data.update({"from_state_id": source.id, "to_state_id": source.id})
    role_refs = _template_role_refs(db, data)
    changed = False
    if transition is None:
        transition = WorkflowTransition(definition_id=definition.id, **data)
        db.add(transition)
        db.flush()
        changed = True
    else:
        for field, value in data.items():
            if getattr(transition, field) != value:
                setattr(transition, field, value)
                changed = True
        if transition.auto_disabled_by_state:
            transition.auto_disabled_by_state = False
            changed = True
    existing_role_refs = {
        purpose: [role_id for (role_id,) in db.query(WorkflowTransitionRole.role_id).filter(
            WorkflowTransitionRole.transition_id == transition.id,
            WorkflowTransitionRole.purpose == purpose,
        ).order_by(WorkflowTransitionRole.sort_order.asc(), WorkflowTransitionRole.id.asc()).all()]
        for purpose in role_refs
    }
    if existing_role_refs != role_refs:
        _replace_transition_role_refs(db, transition.id, role_refs)
        changed = True
    return changed


def _template_condition_config(config: dict | list | None, state_by_ref: dict[str, WorkflowState]):
    if not config or not isinstance(config, dict):
        return config
    result = dict(config)
    if isinstance(result.get("routes"), dict):
        result["routes"] = {key: state_by_ref[value].id for key, value in result["routes"].items()}
    owner_targets = result.pop("target_status_by_owner", None)
    if owner_targets is not None:
        result["target_state_id_by_owner"] = {
            key: state_by_ref[value].id for key, value in owner_targets.items()
        }
    return result


def _default_template_specs() -> list[dict]:
    return [
        {
            "template_key": "requirement.default",
            "object_type": "requirement",
            "name": "默认需求工作流模板",
            "description": "系统内置的需求默认工作流模板。",
            "graph": _requirement_graph(),
        },
        {
            "template_key": "task.default",
            "object_type": "task",
            "name": "默认任务工作流模板",
            "description": "系统内置的任务默认工作流模板。",
            "graph": _task_graph(),
        },
        {
            "template_key": "bug.default",
            "object_type": "bug",
            "name": "默认缺陷工作流模板",
            "description": "系统内置的缺陷默认工作流模板。",
            "graph": _bug_graph(),
        },
        {
            "template_key": "iteration.default",
            "object_type": "iteration",
            "name": "默认迭代工作流模板",
            "description": "系统内置的迭代默认工作流模板。",
            "graph": _iteration_graph(),
        },
        {
            "template_key": "project.default",
            "object_type": "project",
            "name": "默认项目工作流模板",
            "description": "系统内置的项目默认工作流模板。",
            "graph": _project_graph(),
        },
    ]


def _requirement_graph() -> WorkflowGraphSave:
    return WorkflowGraphSave(
        states=[
            _state("pending_assignment", "待分派", "start", "#6b7280", 80, 100, state_role="unassigned"),
            _state("waiting_iteration", "待开始", "normal", "#7c3aed", 280, 100, state_role="waiting_iteration"),
            _state("in_processing", "处理中", "normal", "#2563eb", 480, 100, state_role="active_work"),
            _state("pending_confirmation", "待确认", "normal", "#7c3aed", 480, 100),
            _state("pending_review", "待评审", "normal", "#d97706", 400, 220),
            _state("completed", "已完成", "terminal", "#059669", 680, 100, terminal_kind="completed"),
            _state("canceled", "已取消", "terminal", "#94a3b8", 480, 240, terminal_kind="terminated"),
        ],
        transitions=[
            _transition(
                "claim",
                "认领",
                "pending_assignment",
                "waiting_iteration",
                allowed_roles="project_member",
                target_type="actor",
                handler_scope="project_member",
                condition_config=_assignment_target_state_roles(),
            ),
            _transition(
                "assign", "指派", "pending_assignment", "waiting_iteration",
                target_type="explicit_owner", condition_config=_assignment_target_state_roles(),
            ),
            _iteration_start_transition("waiting_iteration", "in_processing"),
            _unassign_transition("waiting_iteration", "pending_assignment"),
            _unassign_transition("in_processing", "pending_assignment"),
            _command_transition("edit", "编辑", "pending_assignment", allowed_roles="creator", command_type="edit"),
            _command_transition(
                "add_information",
                "补充信息",
                "pending_assignment",
                allowed_roles="project_member,creator",
                command_type="add_information",
            ),
            _transition(
                "submit_review",
                "提交评审",
                "in_processing",
                "pending_review",
                target_type="keep_current",
                handler_scope="current_handler",
                ui_config={"list_display": "primary", "list_priority": 5, "requires_owner": True},
            ),
            _transition(
                "approve_review",
                "评审通过",
                "pending_review",
                "completed",
                allowed_roles="development_lead",
                target_type="keep_current",
                handler_scope="allowed_identity",
            ),
            _transition(
                "reject_review",
                "评审驳回",
                "pending_review",
                "in_processing",
                allowed_roles="development_lead",
                target_type="keep_current",
                handler_scope="allowed_identity",
            ),
            _transition(
                "complete",
                "完成",
                "in_processing",
                "completed",
                target_type="keep_current",
                validator_config={"type": "requirement_terminal_gate", "block_on_open_bugs": True, "block_on_open_tasks": True},
                handler_scope="current_handler",
                ui_config={"list_display": "primary", "list_priority": 10, "requires_owner": True},
            ),
            _ownership_transition("transfer", "转派", "in_processing"),
            _ownership_transition("change_handler", "变更处理人", "in_processing", management=True),
            _ownership_transition("transfer_confirmation", "转移确认", "pending_confirmation"),
            _ownership_transition(
                "change_confirmation_handler",
                "变更确认处理人",
                "pending_confirmation",
                management=True,
            ),
            _command_transition(
                "add_information",
                "补充信息",
                "in_processing",
                allowed_roles="project_member,creator",
                command_type="add_information",
            ),
            _command_transition(
                "add_information",
                "补充信息",
                "pending_confirmation",
                allowed_roles="project_member,creator",
                command_type="add_information",
            ),
            _transition(
                "cancel",
                "取消",
                "pending_assignment",
                "canceled",
                allowed_roles="creator,project_owner",
                target_type="keep_current",
                validator_config={"type": "requirement_terminal_gate", "block_on_open_bugs": True, "block_on_open_tasks": True},
                handler_scope="allowed_identity",
                ui_config={"list_display": "more", "list_priority": 90, "button_type": "danger"},
            ),
            _transition(
                "cancel",
                "取消",
                "in_processing",
                "canceled",
                allowed_roles="current_handler,project_owner",
                target_type="keep_current",
                validator_config={"type": "requirement_terminal_gate", "block_on_open_bugs": True, "block_on_open_tasks": True},
                handler_scope="allowed_identity",
                ui_config={"list_display": "more", "list_priority": 90, "button_type": "danger", "requires_owner": True},
            ),
            _transition(
                "cancel",
                "取消",
                "pending_confirmation",
                "canceled",
                allowed_roles="current_handler,project_owner",
                target_type="keep_current",
                validator_config={"type": "requirement_terminal_gate", "block_on_open_bugs": True, "block_on_open_tasks": True},
                handler_scope="allowed_identity",
                ui_config={"list_display": "more", "list_priority": 90, "button_type": "danger", "requires_owner": True},
            ),
            _reactivate_transition("canceled", allowed_roles="creator,project_owner"),
            _reactivate_transition("completed", allowed_roles="creator,project_owner"),
            _command_transition(
                "view_history",
                "查看历史",
                "canceled",
                allowed_roles="project_member,creator",
                command_type="view_history",
            ),
            _command_transition(
                "add_information",
                "补充信息",
                "canceled",
                allowed_roles="project_member,creator",
                command_type="add_information",
            ),
            _command_transition(
                "view_history",
                "查看历史",
                "completed",
                allowed_roles="project_member,creator",
                command_type="view_history",
            ),
        ],
    )


def _task_graph() -> WorkflowGraphSave:
    return WorkflowGraphSave(
        states=[
            _state("pending_assignment", "待分派", "start", "#6b7280", 80, 120, state_role="unassigned"),
            _state("waiting_iteration", "待开始", "normal", "#7c3aed", 280, 120, state_role="waiting_iteration"),
            _state("in_processing", "处理中", "normal", "#2563eb", 480, 120, state_role="active_work"),
            _state("pending_confirmation", "待确认", "normal", "#7c3aed", 480, 120),
            _state("pending_review", "待评审", "normal", "#d97706", 400, 240),
            _state("completed", "已完成", "terminal", "#059669", 680, 120, terminal_kind="completed"),
            _state("canceled", "已取消", "terminal", "#94a3b8", 480, 260, terminal_kind="terminated"),
        ],
        transitions=[
            _transition(
                "claim",
                "认领",
                "pending_assignment",
                "waiting_iteration",
                allowed_roles="project_member",
                target_type="actor",
                handler_scope="project_member",
                condition_config=_assignment_target_state_roles(),
            ),
            _transition(
                "assign", "指派", "pending_assignment", "waiting_iteration",
                target_type="explicit_owner", condition_config=_assignment_target_state_roles(),
            ),
            _iteration_start_transition("waiting_iteration", "in_processing"),
            _unassign_transition("waiting_iteration", "pending_assignment"),
            _unassign_transition("in_processing", "pending_assignment"),
            _command_transition("edit", "编辑", "pending_assignment", allowed_roles="creator", command_type="edit"),
            _command_transition(
                "add_information",
                "补充信息",
                "pending_assignment",
                allowed_roles="project_member,creator",
                command_type="add_information",
            ),
            _transition(
                "submit_review",
                "提交评审",
                "in_processing",
                "pending_review",
                target_type="keep_current",
                handler_scope="current_handler",
                ui_config={"list_display": "primary", "list_priority": 5, "requires_owner": True},
            ),
            _transition(
                "approve_review",
                "评审通过",
                "pending_review",
                "pending_confirmation",
                allowed_roles="development_lead",
                target_type="keep_current",
                handler_scope="allowed_identity",
            ),
            _transition(
                "reject_review",
                "评审驳回",
                "pending_review",
                "in_processing",
                allowed_roles="development_lead",
                target_type="keep_current",
                handler_scope="allowed_identity",
            ),
            _transition(
                "complete",
                "完成",
                "in_processing",
                "completed",
                target_type="keep_current",
                condition_config={"task_types": ["requirement_implementation", "standalone_operation"]},
                validator_config={"type": "task_descendants_terminal_gate"},
                handler_scope="current_handler",
                ui_config={"list_display": "primary", "list_priority": 10, "requires_owner": True},
            ),
            _transition(
                "submit_confirmation",
                "提交确认",
                "in_processing",
                "pending_confirmation",
                target_type="task_confirmation",
                fallback_type="project_role",
                fallback_roles="project_owner",
                condition_config={"task_types": ["bug_fix", "test_support"]},
                handler_scope="current_handler",
                ui_config={"list_display": "primary", "list_priority": 10, "requires_owner": True},
            ),
            _ownership_transition("transfer", "转派", "in_processing"),
            _ownership_transition("change_handler", "变更处理人", "in_processing", management=True),
            _command_transition(
                "add_information",
                "补充信息",
                "in_processing",
                allowed_roles="project_member,creator",
                command_type="add_information",
            ),
            _transition(
                "approve_confirmation",
                "确认通过",
                "pending_confirmation",
                "completed",
                target_type="keep_current",
                validator_config={"type": "task_descendants_terminal_gate"},
                handler_scope="current_handler",
                ui_config={"list_display": "primary", "list_priority": 10, "requires_owner": True},
            ),
            _transition(
                "return_rework",
                "退回返工",
                "pending_confirmation",
                "in_processing",
                target_type="previous_handler",
                handler_scope="current_handler",
                form_config={"fields": [{"field": "reason", "label": "退回原因", "type": "textarea", "required": True}]},
                ui_config={"list_display": "more", "list_priority": 20, "requires_owner": True},
            ),
            _ownership_transition("transfer_confirmation", "转移确认", "pending_confirmation"),
            _ownership_transition(
                "change_confirmation_handler",
                "变更确认处理人",
                "pending_confirmation",
                management=True,
            ),
            _command_transition(
                "add_information",
                "补充信息",
                "pending_confirmation",
                allowed_roles="project_member,creator",
                command_type="add_information",
            ),
            _transition(
                "cancel",
                "取消",
                "pending_assignment",
                "canceled",
                allowed_roles="creator,project_owner",
                target_type="keep_current",
                validator_config={"type": "task_descendants_terminal_gate"},
                handler_scope="allowed_identity",
                ui_config={"button_type": "danger", "list_display": "more", "list_priority": 90},
            ),
            _transition(
                "cancel",
                "取消",
                "in_processing",
                "canceled",
                allowed_roles="current_handler,project_owner",
                target_type="keep_current",
                validator_config={"type": "task_descendants_terminal_gate"},
                handler_scope="allowed_identity",
                ui_config={"button_type": "danger", "list_display": "more", "list_priority": 90, "requires_owner": True},
            ),
            _transition(
                "cancel",
                "取消",
                "pending_confirmation",
                "canceled",
                allowed_roles="project_owner",
                target_type="keep_current",
                validator_config={"type": "task_descendants_terminal_gate"},
                handler_scope="allowed_identity",
                ui_config={"button_type": "danger", "list_display": "more", "list_priority": 90, "requires_owner": True},
            ),
            _reactivate_transition("canceled", allowed_roles="creator,project_owner"),
            _command_transition(
                "view_history",
                "查看历史",
                "canceled",
                allowed_roles="project_member,creator",
                command_type="view_history",
            ),
            _command_transition(
                "add_information",
                "补充信息",
                "canceled",
                allowed_roles="project_member,creator",
                command_type="add_information",
            ),
        ],
    )


def _bug_graph() -> WorkflowGraphSave:
    return WorkflowGraphSave(
        states=[
            _state("pending_handling", "待分派", "start", "#6b7280", 80, 100, state_role="unassigned"),
            _state("waiting_iteration", "待开始", "normal", "#7c3aed", 280, 100, state_role="waiting_iteration"),
            _state("fixing", "修复中", "normal", "#2563eb", 480, 100, state_role="active_work"),
            _state("pending_verification", "待验证", "normal", "#7c3aed", 480, 100),
            _state("pending_review", "待评审", "normal", "#d97706", 400, 220),
            _state("verified", "已验证", "normal", "#0f766e", 680, 100),
            _state("closed", "已关闭", "terminal", "#059669", 880, 100, terminal_kind="completed"),
        ],
        transitions=[
            _transition(
                "claim",
                "认领",
                "pending_handling",
                "waiting_iteration",
                allowed_roles="project_member",
                target_type="actor",
                handler_scope="project_member",
                condition_config=_assignment_target_state_roles(),
                ui_config={"list_display": "primary", "list_priority": 5, "ownerless_only": True},
            ),
            _transition(
                "assign",
                "指派",
                "pending_handling",
                "waiting_iteration",
                allowed_roles="project_owner",
                target_type="explicit_owner",
                allow_manual_owner=True,
                condition_config=_assignment_target_state_roles(),
                ui_config={"list_display": "more", "list_priority": 10, "ownerless_only": True},
            ),
            _iteration_start_transition("waiting_iteration", "fixing"),
            _unassign_transition("waiting_iteration", "pending_handling"),
            _unassign_transition("fixing", "pending_handling"),
            _command_transition("edit", "编辑", "pending_handling", allowed_roles="creator", command_type="edit"),
            _ownership_transition("transfer", "转派", "waiting_iteration"),
            _ownership_transition("change_handler", "变更处理人", "waiting_iteration", management=True),
            _command_transition("edit", "编辑", "waiting_iteration", allowed_roles="creator", command_type="edit"),
            _bug_confirmation_transition(),
            _bug_void_transition("pending_handling"),
            _command_transition(
                "add_information",
                "补充信息",
                "pending_handling",
                allowed_roles="reporter,tester",
                command_type="add_information",
            ),
            _transition(
                "submit_review",
                "提交评审",
                "fixing",
                "pending_review",
                target_type="keep_current",
                handler_scope="current_handler",
                ui_config={"list_display": "primary", "list_priority": 5, "requires_owner": True},
            ),
            _transition(
                "approve_review",
                "评审通过",
                "pending_review",
                "pending_verification",
                allowed_roles="development_lead",
                target_type="keep_current",
                handler_scope="allowed_identity",
            ),
            _transition(
                "reject_review",
                "评审驳回",
                "pending_review",
                "fixing",
                allowed_roles="development_lead",
                target_type="keep_current",
                handler_scope="allowed_identity",
            ),
            _transition(
                "reclassify_bug_type",
                "重新判定缺陷类型",
                "fixing",
                "fixing",
                target_type="keep_current",
                condition_config={
                    "routing_mode": "automatic_with_override",
                    "field": "bug_type",
                    "route_dictionary": "bug_type",
                    "allow_override_roles": ["project_owner", "system_admin"],
                },
                form_config={
                    "fields": [
                        {"field": "bug_type", "label": "Bug 类型", "type": "select", "dictionary": "bug_type", "required": True},
                        {"field": "reason", "label": "重分类原因", "type": "textarea", "required": True},
                    ]
                },
                handler_scope="current_handler",
                ui_config={"list_display": "more", "list_priority": 40, "requires_owner": True},
            ),
            _transition(
                "submit_verification",
                "提交验证",
                "fixing",
                "pending_verification",
                target_type="bug_verifier",
                fallback_type="project_role",
                fallback_roles="project_owner",
                handler_scope="current_handler",
                ui_config={"list_display": "primary", "list_priority": 10, "requires_owner": True},
            ),
            _ownership_transition("transfer", "转派", "fixing"),
            _ownership_transition("change_handler", "变更处理人", "fixing", management=True),
            _bug_void_transition("fixing"),
            _command_transition(
                "add_information",
                "补充信息",
                "fixing",
                allowed_roles="reporter,tester",
                command_type="add_information",
            ),
            _transition(
                "verification_passed",
                "验证通过",
                "pending_verification",
                "verified",
                handler_scope="current_handler",
                ui_config={"list_display": "primary", "list_priority": 10, "requires_owner": True},
            ),
            _transition(
                "verification_failed",
                "验证不通过",
                "pending_verification",
                "pending_handling",
                target_type="previous_handler",
                handler_scope="current_handler",
                form_config={"fields": [{"field": "reason", "label": "验证不通过原因", "type": "textarea", "required": True}]},
                ui_config={"list_display": "primary", "list_priority": 20, "requires_owner": True},
            ),
            _ownership_transition("transfer_verification", "转移验证", "pending_verification"),
            _ownership_transition("assign_verifier", "指派验证人", "pending_verification", management=True),
            _bug_void_transition("pending_verification"),
            _command_transition(
                "add_information",
                "补充信息",
                "pending_verification",
                allowed_roles="reporter,tester",
                command_type="add_information",
            ),
            _transition(
                "return_reopen",
                "退回打开",
                "verified",
                "pending_handling",
                allowed_roles="reporter,tester,project_owner",
                target_type="keep_current",
                allow_manual_owner=True,
                handler_scope="allowed_identity",
                form_config={"fields": [{"field": "reason", "label": "退回原因", "type": "textarea", "required": True}]},
                ui_config={"list_display": "more", "list_priority": 20},
            ),
            _transition(
                "close",
                "关闭",
                "verified",
                "closed",
                allowed_roles="current_handler,project_owner",
                target_type="keep_current",
                validator_config={"type": "bug_close_gate", "direct_tasks_terminal_statuses": ["completed", "canceled"]},
                handler_scope="allowed_identity",
                ui_config={"list_display": "primary", "list_priority": 10, "requires_owner": True},
            ),
            _command_transition(
                "add_information",
                "补充信息",
                "verified",
                allowed_roles="project_member,reporter,tester",
                command_type="add_information",
            ),
            _command_transition(
                "view_history",
                "查看历史",
                "verified",
                allowed_roles="project_member,reporter,tester",
                command_type="view_history",
            ),
            _transition(
                "activate",
                "激活",
                "closed",
                "pending_handling",
                allowed_roles="reporter,tester,project_owner",
                target_type="previous_handler",
                allow_unassigned=True,
                handler_scope="allowed_identity",
                form_config={"fields": [{"field": "reason", "label": "激活原因", "type": "textarea", "required": True}]},
                ui_config={"list_display": "primary", "list_priority": 10},
            ),
            _command_transition(
                "add_information",
                "补充信息",
                "closed",
                allowed_roles="project_member,reporter,tester",
                command_type="add_information",
            ),
            _command_transition(
                "view_history",
                "查看历史",
                "closed",
                allowed_roles="project_member,reporter,tester",
                command_type="view_history",
            ),
        ],
    )


def _iteration_graph() -> WorkflowGraphSave:
    return WorkflowGraphSave(
        states=[
            _state("planning", "规划中", "start", "#6b7280", 80, 120),
            _state("active", "进行中", "normal", "#2563eb", 280, 120),
            _state("completed", "已完成", "terminal", "#059669", 480, 120, terminal_kind="completed"),
            _state("canceled", "已取消", "terminal", "#94a3b8", 480, 260, terminal_kind="terminated"),
        ],
        transitions=[
            _transition(
                "start",
                "开始",
                "planning",
                "active",
                form_config={"fields": [{"field": "effective_time", "label": "实际开始日期", "type": "date", "required": True}]},
            ),
            _transition("complete", "完成", "active", "completed", validator_config={"type": "iteration_terminal_gate"}),
            _transition("cancel", "取消", "active", "canceled", validator_config={"type": "iteration_terminal_gate"}),
        ],
    )


def _project_graph() -> WorkflowGraphSave:
    return WorkflowGraphSave(
        states=[
            _state("planning", "规划中", "start", "#6b7280", 80, 120),
            _state("active", "进行中", "normal", "#2563eb", 280, 120),
            _state("paused", "已暂停", "normal", "#7c3aed", 480, 120),
            _state("closed", "已关闭", "terminal", "#059669", 680, 120, terminal_kind="completed"),
        ],
        transitions=[
            _transition(
                "start",
                "启动",
                "planning",
                "active",
                form_config={"fields": [{"field": "effective_time", "label": "实际开始日期", "type": "date", "required": True}]},
                ui_config={"list_display": "primary", "list_priority": 10, "button_type": "success"},
            ),
            _transition("suspend", "暂停", "active", "paused"),
            _transition("resume", "恢复", "paused", "active"),
            _transition(
                "close",
                "关闭",
                "active",
                "closed",
                validator_config={"type": "project_close_gate"},
                form_config={"fields": [{"field": "effective_time", "label": "实际完成日期", "type": "date", "required": True}]},
            ),
            _transition(
                "close",
                "关闭",
                "paused",
                "closed",
                validator_config={"type": "project_close_gate"},
                form_config={"fields": [{"field": "effective_time", "label": "实际完成日期", "type": "date", "required": True}]},
            ),
            _transition("activate", "激活", "closed", "active"),
        ],
    )


def _state(
    ref: str,
    status_name: str,
    category: str,
    color: str,
    x: int,
    y: int,
    terminal_kind: str | None = None,
    state_role: str | None = None,
) -> WorkflowStateBase:
    return WorkflowStateBase(
        ref=ref,
        status_name=status_name,
        category=category,
        terminal_kind=terminal_kind,
        state_role=state_role,
        color=color,
        x=x,
        y=y,
    )


def _assignment_target_state_roles() -> dict:
    return {
        "target_state_role_by_iteration_phase": {
            "active": "active_work",
            "inactive": "waiting_iteration",
        }
    }


def _iteration_start_transition(from_ref: str, to_ref: str) -> WorkflowTransitionBase:
    return _transition(
        "start_iteration",
        "迭代启动",
        from_ref,
        to_ref,
        target_type="keep_current",
        trigger_config={"type": "system_action"},
        ui_config={"list_display": "more", "list_priority": 1},
    )


def _unassign_transition(from_ref: str, to_ref: str) -> WorkflowTransitionBase:
    return _transition(
        "unassign",
        "取消指派",
        from_ref,
        to_ref,
        allowed_roles="current_handler,project_owner",
        target_type="none",
        fallback_type="none",
        handler_scope="allowed_identity",
        ui_config={"list_display": "more", "list_priority": 60, "action_category": "management", "requires_owner": True},
    )


def _transition(
    action_key: str,
    action_name: str,
    from_ref: str,
    to_ref: str,
    *,
    allowed_roles: str = "",
    target_type: str = "keep_current",
    target_roles: str = "",
    fallback_type: str = "keep_current",
    fallback_roles: str = "",
    allow_manual_owner: bool = False,
    allow_unassigned: bool = False,
    manual_owner_roles: str = "",
    condition_config: dict | None = None,
    validator_config: dict | None = None,
    form_config: dict | None = None,
    ui_config: dict | None = None,
    handler_scope: str | None = None,
    trigger_config: dict | None = None,
) -> WorkflowTransitionBase:
    resolved_allowed_roles = allowed_roles
    resolved_allow_manual_owner = allow_manual_owner
    resolved_ui_config = dict(ui_config or {})
    resolved_ui_config.setdefault("action_category", "process")
    if handler_scope:
        resolved_ui_config["handler_scope"] = handler_scope
    if action_key in {"claim", "assign"} and from_ref in {"pending_assignment", "pending_handling"}:
        if action_key == "claim":
            resolved_ui_config["handler_scope"] = handler_scope or "project_member"
            resolved_ui_config["action_category"] = "ownership"
            resolved_ui_config.setdefault("list_display", "primary")
            resolved_ui_config.setdefault("list_priority", 10)
        if action_key == "assign":
            resolved_allowed_roles = resolved_allowed_roles or "project_owner"
            resolved_allow_manual_owner = True
            resolved_ui_config["handler_scope"] = handler_scope or "allowed_identity"
            resolved_ui_config["action_category"] = "management"
            resolved_ui_config.setdefault("list_display", "more")
            resolved_ui_config.setdefault("list_priority", 20)
    sort_order = int(resolved_ui_config.pop("list_priority", 100))
    return WorkflowTransitionBase(
        action_key=action_key,
        action_name=action_name,
        from_ref=from_ref,
        to_ref=to_ref,
        allowed_roles=resolved_allowed_roles,
        handler_rule={
            "target_type": target_type,
            "target_roles": target_roles,
            "fallback_type": fallback_type,
            "fallback_roles": fallback_roles,
            "allow_manual_owner": resolved_allow_manual_owner,
            "allow_unassigned": allow_unassigned,
            "manual_owner_roles": manual_owner_roles,
        },
        trigger_config=trigger_config,
        condition_config=condition_config,
        validator_config=validator_config,
        form_config=form_config,
        ui_config=resolved_ui_config,
        sort_order=sort_order,
    )


def _ownership_transition(
    action_key: str,
    action_name: str,
    current_status: str,
    *,
    management: bool = False,
) -> WorkflowTransitionBase:
    return _transition(
        action_key,
        action_name,
        current_status,
        current_status,
        allowed_roles="project_owner" if management else "",
        target_type="explicit_owner",
        allow_manual_owner=True,
        form_config={
            "title": action_name,
            "fields": [
                {"field": "reason", "label": "原因", "type": "textarea", "required": False},
            ],
        },
        ui_config={
            "button_type": "warning" if management else "primary",
            "list_display": "more",
            "list_priority": 70 if management else 60,
            "action_category": "management" if management else "ownership",
            "handler_scope": "allowed_identity" if management else "current_handler",
            "requires_owner": True,
        },
    )


def _command_transition(
    action_key: str,
    action_name: str,
    current_status: str,
    *,
    allowed_roles: str,
    command_type: str,
) -> WorkflowTransitionBase:
    fields = []
    if command_type == "add_information":
        fields = [{"field": "content", "label": "补充内容", "type": "textarea", "required": True}]
    return _transition(
        action_key,
        action_name,
        current_status,
        current_status,
        allowed_roles=allowed_roles,
        handler_scope="allowed_identity",
        form_config={"fields": fields} if fields else None,
        ui_config={
            "command_type": command_type,
            "action_category": "information" if command_type == "add_information" else "navigation",
            "button_type": "primary",
            "list_display": "more",
            "list_priority": 80,
        },
    )


def _reactivate_transition(from_ref: str, *, allowed_roles: str) -> WorkflowTransitionBase:
    return _transition(
        "reactivate",
        "重新激活",
        from_ref,
        "pending_assignment",
        allowed_roles=allowed_roles,
        target_type="keep_current",
        allow_manual_owner=True,
        condition_config={
            "target_status_by_owner": {
                "with_owner": "in_processing",
                "without_owner": "pending_assignment",
            }
        },
        handler_scope="allowed_identity",
        form_config={"fields": [{"field": "reason", "label": "重新激活原因", "type": "textarea", "required": True}]},
        ui_config={"list_display": "primary", "list_priority": 10},
    )


def _bug_void_transition(from_ref: str) -> WorkflowTransitionBase:
    return _transition(
        "void_close",
        "作废/关闭",
        from_ref,
        "closed",
        allowed_roles="project_owner",
        target_type="keep_current",
        validator_config={"type": "bug_close_gate", "direct_tasks_terminal_statuses": ["completed", "canceled"]},
        handler_scope="allowed_identity",
        form_config={"fields": [{"field": "reason", "label": "作废/关闭原因", "type": "textarea", "required": True}]},
        ui_config={
            "button_type": "danger",
            "list_display": "more",
            "list_priority": 90,
            "action_category": "management",
        },
    )


def _bug_confirmation_transition() -> WorkflowTransitionBase:
    return _transition(
        "confirm_bug_type",
        "确认缺陷类型",
        "fixing",
        "fixing",
        target_type="bug_verifier_if_pending_verification",
        condition_config={
            "routing_mode": "automatic",
            "field": "bug_type",
            "route_dictionary": "bug_type",
        },
        form_config={
            "fields": [
                {
                    "field": "bug_type",
                    "label": "Bug 类型",
                    "type": "select",
                    "dictionary": "bug_type",
                    "required": True,
                }
            ]
        },
        handler_scope="current_handler",
        ui_config={"list_display": "primary", "list_priority": 10, "requires_owner": True},
    )
