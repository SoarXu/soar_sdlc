import pytest

from app.services.default_workflow_template_service import graph_for_object_type


@pytest.mark.parametrize(
    ("object_type", "active_status"),
    [
        ("requirement", "处理中"),
        ("task", "处理中"),
        ("bug", "修复中"),
    ],
)
def test_default_work_item_template_defines_assignment_state_roles(object_type: str, active_status: str):
    graph = graph_for_object_type(object_type)
    roles = {state.state_role: state for state in graph.states}

    assert roles["unassigned"].status_name == "待分派"
    assert roles["waiting_iteration"].status_name == "待开始"
    assert roles["active_work"].status_name == active_status

    for action_key in ("claim", "assign"):
        transition = next(item for item in graph.transitions if item.action_key == action_key)
        assert transition.from_ref == roles["unassigned"].ref
        assert transition.condition_config["target_state_role_by_iteration_phase"] == {
            "active": "active_work",
            "inactive": "waiting_iteration",
        }

    activation = next(item for item in graph.transitions if item.action_key == "start_iteration")
    assert activation.from_ref == roles["waiting_iteration"].ref
    assert activation.to_ref == roles["active_work"].ref
    assert activation.trigger_config == {"type": "system_action"}

    unassign_sources = {
        item.from_ref
        for item in graph.transitions
        if item.action_key == "unassign"
    }
    assert unassign_sources == {roles["waiting_iteration"].ref, roles["active_work"].ref}
    assert all(
        item.to_ref == roles["unassigned"].ref and item.handler_rule["target_type"] == "none"
        for item in graph.transitions
        if item.action_key == "unassign"
    )
