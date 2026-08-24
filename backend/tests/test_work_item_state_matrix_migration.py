import pytest

from app.db.session import SessionLocal
from app.models.workflow_definition import WorkflowDefinition, WorkflowState, WorkflowTransition
from app.services.default_workflow_template_service import reconcile_work_item_state_matrix


@pytest.mark.parametrize("object_type", ["requirement", "task", "bug"])
def test_reconcile_work_item_state_matrix_upgrades_recognized_legacy_graph(object_type: str):
    with SessionLocal() as db:
        definition = WorkflowDefinition(
            name=f"Legacy {object_type} state matrix",
            object_type=object_type,
            scope_type="system",
            template_key=f"test.{object_type}.legacy",
            is_default_template=False,
            enabled=False,
        )
        db.add(definition)
        db.flush()
        unassigned = WorkflowState(
            definition_id=definition.id,
            status_name="Legacy unassigned",
            category="start",
            color="#6b7280",
            enabled=True,
        )
        active = WorkflowState(
            definition_id=definition.id,
            status_name="Legacy active",
            category="normal",
            color="#2563eb",
            enabled=True,
        )
        db.add_all([unassigned, active])
        db.flush()
        definition.initial_state_id = unassigned.id
        transitions = [
            WorkflowTransition(
                definition_id=definition.id,
                action_key="claim",
                action_name="认领",
                from_state_id=unassigned.id,
                to_state_id=unassigned.id if object_type == "bug" else active.id,
                allowed_roles="project_member",
                handler_rule={"target_type": "actor"},
                enabled=True,
            ),
            WorkflowTransition(
                definition_id=definition.id,
                action_key="assign",
                action_name="指派",
                from_state_id=unassigned.id,
                to_state_id=unassigned.id if object_type == "bug" else active.id,
                handler_rule={"target_type": "explicit_owner"},
                enabled=True,
            ),
        ]
        if object_type == "bug":
            transitions.append(
                WorkflowTransition(
                    definition_id=definition.id,
                    action_key="confirm_bug_type",
                    action_name="确认缺陷类型",
                    from_state_id=unassigned.id,
                    to_state_id=active.id,
                    handler_rule={"target_type": "keep_current"},
                    enabled=True,
                )
            )
        db.add_all(transitions)
        db.commit()

        assert reconcile_work_item_state_matrix(db, definition) is True
        db.commit()

        states = db.query(WorkflowState).filter(WorkflowState.definition_id == definition.id).all()
        states_by_role = {state.state_role: state for state in states}
        assert set(states_by_role) >= {"unassigned", "waiting_iteration", "active_work"}
        assert states_by_role["unassigned"].id == unassigned.id
        assert states_by_role["active_work"].id == active.id

        transitions = db.query(WorkflowTransition).filter(WorkflowTransition.definition_id == definition.id).all()
        waiting = states_by_role["waiting_iteration"]
        for action_key in ("claim", "assign"):
            transition = next(item for item in transitions if item.action_key == action_key)
            assert transition.to_state_id == waiting.id
            assert transition.condition_config["target_state_role_by_iteration_phase"] == {
                "active": "active_work",
                "inactive": "waiting_iteration",
            }
        assert any(
            item.action_key == "start_iteration"
            and item.from_state_id == waiting.id
            and item.to_state_id == active.id
            and item.trigger_config == {"type": "system_action"}
            for item in transitions
        )
        assert {
            item.from_state_id
            for item in transitions
            if item.action_key == "unassign" and item.to_state_id == unassigned.id
        } == {waiting.id, active.id}

        assert reconcile_work_item_state_matrix(db, definition) is False
