from pathlib import Path

import pytest

from app.db.session import SessionLocal
from app.models.workflow_definition import WorkflowDefinition, WorkflowState, WorkflowTransition
from app.services.default_workflow_template_service import (
    reconcile_bug_action_matrix,
    reconcile_managed_bug_action_matrices,
)
from app.services.workflow_definition_service import save_graph
from app.views.workflow_definition_view import WorkflowGraphSave


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "20260822_003_align_bug_workflow_actions.py"
)
FOLLOW_UP_MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "20260822_004_align_bug_confirmation_state.py"
)
DEDUPLICATION_MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "20260824_001_deduplicate_bug_confirmation_transitions.py"
)


def _create_definition(db, *, template_key: str | None, scope_type: str = "system") -> WorkflowDefinition:
    definition = WorkflowDefinition(
        name=f"Bug action matrix {template_key or scope_type}",
        object_type="bug",
        scope_type=scope_type,
        template_key=template_key,
        is_default_template=template_key == "bug.default",
        enabled=True,
        version=1,
    )
    db.add(definition)
    db.flush()
    return definition


def _add_state(db, definition: WorkflowDefinition, state_role: str) -> WorkflowState:
    state = WorkflowState(
        definition_id=definition.id,
        status_name=f"test {state_role}",
        category="start" if state_role == "unassigned" else "normal",
        state_role=state_role,
        color="#2563eb",
        x=0,
        y=0,
        sort_order=10,
        enabled=True,
    )
    db.add(state)
    db.flush()
    return state


def _add_transition(db, definition: WorkflowDefinition, action_key: str, state: WorkflowState) -> WorkflowTransition:
    transition = WorkflowTransition(
        definition_id=definition.id,
        action_key=action_key,
        action_name=action_key,
        from_state_id=state.id,
        to_state_id=state.id,
        allowed_roles="",
        handler_rule={"target_type": "keep_current"},
        enabled=True,
        sort_order=10,
    )
    db.add(transition)
    db.flush()
    return transition


def _delete_definition(db, definition_id: int) -> None:
    state_ids = [
        state_id
        for (state_id,) in db.query(WorkflowState.id).filter(WorkflowState.definition_id == definition_id).all()
    ]
    db.query(WorkflowDefinition).filter(WorkflowDefinition.id == definition_id).update(
        {WorkflowDefinition.initial_state_id: None}
    )
    db.flush()
    db.query(WorkflowTransition).filter(WorkflowTransition.definition_id == definition_id).delete()
    if state_ids:
        db.query(WorkflowState).filter(WorkflowState.id.in_(state_ids)).delete()
    db.query(WorkflowDefinition).filter(WorkflowDefinition.id == definition_id).delete()
    db.commit()


def _persisted_graph_payload(db, definition: WorkflowDefinition) -> WorkflowGraphSave:
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
    return WorkflowGraphSave.model_validate(
        {
            "initial_state_id": definition.initial_state_id,
            "states": [
                {
                    "id": state.id,
                    "status_name": state.status_name,
                    "category": state.category,
                    "state_role": state.state_role,
                    "terminal_kind": state.terminal_kind,
                    "color": state.color,
                    "x": state.x,
                    "y": state.y,
                    "sort_order": state.sort_order,
                    "enabled": state.enabled,
                }
                for state in states
            ],
            "transitions": [
                {
                    "id": transition.id,
                    "action_name": transition.action_name,
                    "from_state_id": transition.from_state_id,
                    "to_state_id": transition.to_state_id,
                    "allowed_roles": transition.allowed_roles,
                    "handler_rule": transition.handler_rule,
                    "trigger_config": transition.trigger_config,
                    "condition_config": transition.condition_config,
                    "validator_config": transition.validator_config,
                    "post_action_config": transition.post_action_config,
                    "ui_config": transition.ui_config,
                    "form_config": transition.form_config,
                    "diagram_config": transition.diagram_config,
                    "enabled": transition.enabled,
                    "auto_disabled_by_state": transition.auto_disabled_by_state,
                    "sort_order": transition.sort_order,
                }
                for transition in transitions
            ],
        }
    )


def test_bug_action_alignment_migration_declares_n002_dependency():
    assert MIGRATION_PATH.exists()
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'revision = "20260822_003"' in source
    assert 'down_revision = "20260822_002"' in source
    assert "reconcile_managed_bug_action_matrices" in source


def test_bug_confirmation_alignment_follow_up_migration_runs_after_n004():
    assert FOLLOW_UP_MIGRATION_PATH.exists()
    source = FOLLOW_UP_MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'revision = "20260822_004"' in source
    assert 'down_revision = "20260822_003"' in source
    assert "reconcile_managed_bug_action_matrices" in source


def test_bug_confirmation_deduplication_migration_runs_after_task_terminal_gate():
    assert DEDUPLICATION_MIGRATION_PATH.exists()
    source = DEDUPLICATION_MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'revision = "20260824_001"' in source
    assert 'down_revision = "20260822_006"' in source
    assert "reconcile_managed_bug_action_matrices" in source


def test_reconcile_bug_action_matrix_is_role_based_and_idempotent():
    with SessionLocal() as db:
        definition = _create_definition(db, template_key="bug.default")
        unassigned = _add_state(db, definition, "unassigned")
        waiting = _add_state(db, definition, "waiting_iteration")
        active = _add_state(db, definition, "active_work")
        definition.initial_state_id = unassigned.id
        _add_transition(db, definition, "claim", unassigned)
        _add_transition(db, definition, "assign", unassigned)
        _add_transition(db, definition, "transfer", unassigned)
        _add_transition(db, definition, "change_handler", unassigned)
        _add_transition(db, definition, "start_iteration", waiting)
        _add_transition(db, definition, "unassign", waiting)
        _add_transition(db, definition, "confirm_bug_type", unassigned)
        _add_transition(db, definition, "transfer", active)
        _add_transition(db, definition, "change_handler", active)
        db.commit()
        try:
            assert reconcile_bug_action_matrix(db, definition) is True
            db.commit()

            transitions = db.query(WorkflowTransition).filter(
                WorkflowTransition.definition_id == definition.id
            ).all()
            by_source_and_key = {
                (transition.from_state_id, transition.action_key): transition
                for transition in transitions
            }
            assert by_source_and_key[(unassigned.id, "transfer")].enabled is False
            assert by_source_and_key[(unassigned.id, "change_handler")].enabled is False
            assert by_source_and_key[(waiting.id, "transfer")].enabled is True
            assert by_source_and_key[(waiting.id, "change_handler")].enabled is True
            assert by_source_and_key[(active.id, "transfer")].enabled is True
            assert by_source_and_key[(active.id, "change_handler")].enabled is True
            assert by_source_and_key[(unassigned.id, "edit")].ui_config["command_type"] == "edit"
            assert by_source_and_key[(waiting.id, "edit")].ui_config["command_type"] == "edit"
            assert (active.id, "edit") not in by_source_and_key
            assert (unassigned.id, "confirm_bug_type") not in by_source_and_key
            assert by_source_and_key[(active.id, "confirm_bug_type")].to_state_id == active.id

            assert reconcile_bug_action_matrix(db, definition) is False
            db.commit()
            assert db.query(WorkflowTransition).filter(
                WorkflowTransition.definition_id == definition.id,
                WorkflowTransition.action_key == "edit",
            ).count() == 2
        finally:
            _delete_definition(db, definition.id)


def test_reconcile_bug_action_matrix_disables_duplicate_active_confirmation_transitions():
    with SessionLocal() as db:
        definition = _create_definition(db, template_key="bug.default")
        unassigned = _add_state(db, definition, "unassigned")
        waiting = _add_state(db, definition, "waiting_iteration")
        active = _add_state(db, definition, "active_work")
        definition.initial_state_id = unassigned.id
        canonical = _add_transition(db, definition, "confirm_bug_type", active)
        duplicate = _add_transition(db, definition, "confirm_bug_type", active)
        canonical.action_name = "确认缺陷类型"
        duplicate.action_name = "确认缺陷类型"
        db.commit()
        try:
            assert reconcile_bug_action_matrix(db, definition) is True
            db.commit()

            confirmations = (
                db.query(WorkflowTransition)
                .filter(
                    WorkflowTransition.definition_id == definition.id,
                    WorkflowTransition.from_state_id == active.id,
                    WorkflowTransition.action_key == "confirm_bug_type",
                )
                .order_by(WorkflowTransition.id.asc())
                .all()
            )
            enabled_confirmations = [transition for transition in confirmations if transition.enabled]
            assert [transition.id for transition in enabled_confirmations] == [canonical.id]
            assert enabled_confirmations[0].action_name == "确认缺陷类型"
            assert enabled_confirmations[0].to_state_id == active.id
            assert duplicate.enabled is False
            assert duplicate.auto_disabled_by_state is False

            saved = save_graph(db, definition.id, _persisted_graph_payload(db, definition))
            assert saved["definition"].id == definition.id

            assert reconcile_bug_action_matrix(db, definition) is False
            db.commit()
        finally:
            _delete_definition(db, definition.id)


def test_reconcile_bug_action_matrix_moves_legacy_confirmation_without_creating_a_duplicate():
    with SessionLocal() as db:
        definition = _create_definition(db, template_key="bug.default")
        unassigned = _add_state(db, definition, "unassigned")
        waiting = _add_state(db, definition, "waiting_iteration")
        active = _add_state(db, definition, "active_work")
        definition.initial_state_id = unassigned.id
        legacy = _add_transition(db, definition, "confirm_bug_type", unassigned)
        legacy.action_name = "确认缺陷类型"
        legacy.to_state_id = active.id
        db.commit()
        try:
            assert reconcile_bug_action_matrix(db, definition) is True
            db.commit()

            confirmations = (
                db.query(WorkflowTransition)
                .filter(
                    WorkflowTransition.definition_id == definition.id,
                    WorkflowTransition.action_key == "confirm_bug_type",
                )
                .order_by(WorkflowTransition.id.asc())
                .all()
            )
            assert [transition.id for transition in confirmations] == [legacy.id]
            assert confirmations[0].from_state_id == active.id
            assert confirmations[0].to_state_id == active.id

            assert reconcile_bug_action_matrix(db, definition) is False
            db.commit()
        finally:
            _delete_definition(db, definition.id)


def test_reconcile_managed_bug_action_matrices_skips_custom_workflow():
    with SessionLocal() as db:
        definition = _create_definition(db, template_key=None, scope_type="assignee_rule_config")
        unassigned = _add_state(db, definition, "unassigned")
        _add_state(db, definition, "waiting_iteration")
        _add_state(db, definition, "active_work")
        custom = _add_transition(db, definition, "custom_transfer", unassigned)
        db.commit()
        try:
            reconcile_managed_bug_action_matrices(db)
            db.commit()
            db.refresh(custom)
            assert custom.enabled is True
            assert db.query(WorkflowTransition).filter(
                WorkflowTransition.definition_id == definition.id,
                WorkflowTransition.action_key == "edit",
            ).count() == 0
        finally:
            _delete_definition(db, definition.id)


def test_reconcile_managed_bug_action_matrices_skips_custom_system_derived_workflow():
    with SessionLocal() as db:
        parent = _create_definition(db, template_key="bug.default")
        parent_unassigned = _add_state(db, parent, "unassigned")
        parent_waiting = _add_state(db, parent, "waiting_iteration")
        parent_active = _add_state(db, parent, "active_work")
        parent.initial_state_id = parent_unassigned.id
        for action_key, state in (
            ("claim", parent_unassigned),
            ("assign", parent_unassigned),
            ("transfer", parent_unassigned),
            ("change_handler", parent_unassigned),
            ("start_iteration", parent_waiting),
            ("unassign", parent_waiting),
            ("transfer", parent_active),
            ("change_handler", parent_active),
            ("unassign", parent_active),
        ):
            _add_transition(db, parent, action_key, state)

        definition = _create_definition(db, template_key=None, scope_type="assignee_rule_config")
        definition.parent_definition_id = parent.id
        unassigned = _add_state(db, definition, "unassigned")
        _add_state(db, definition, "waiting_iteration")
        _add_state(db, definition, "active_work")
        custom = _add_transition(db, definition, "custom_transfer", unassigned)
        db.commit()
        try:
            reconcile_managed_bug_action_matrices(db)
            db.commit()
            db.refresh(custom)
            assert custom.enabled is True
            assert db.query(WorkflowTransition).filter(
                WorkflowTransition.definition_id == definition.id,
                WorkflowTransition.action_key == "edit",
            ).count() == 0
        finally:
            _delete_definition(db, definition.id)
            _delete_definition(db, parent.id)


def test_reconcile_bug_action_matrix_rejects_selected_definition_without_n002_roles():
    with SessionLocal() as db:
        definition = _create_definition(db, template_key="bug.default")
        db.commit()
        try:
            with pytest.raises(RuntimeError, match="state roles"):
                reconcile_bug_action_matrix(db, definition)
        finally:
            _delete_definition(db, definition.id)
