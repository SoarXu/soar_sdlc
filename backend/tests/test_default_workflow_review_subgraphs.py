from app.services.default_workflow_template_service import graph_for_object_type


def test_default_workflows_define_a_development_lead_review_gate():
    expected_successors = {
        "requirement": "completed",
        "task": "pending_confirmation",
        "bug": "pending_verification",
    }
    for object_type, successor in expected_successors.items():
        graph = graph_for_object_type(object_type)
        state_refs = {state.ref for state in graph.states}
        review_transitions = {transition.action_key: transition for transition in graph.transitions}

        assert "pending_review" in state_refs
        assert review_transitions["submit_review"].to_ref == "pending_review"
        assert review_transitions["approve_review"].from_ref == "pending_review"
        assert review_transitions["approve_review"].to_ref == successor
        assert review_transitions["reject_review"].from_ref == "pending_review"
        assert review_transitions["reject_review"].to_ref in {"in_processing", "fixing"}
        assert review_transitions["approve_review"].allowed_roles == "development_lead"
        assert review_transitions["reject_review"].allowed_roles == "development_lead"
        assert review_transitions["submit_review"].trigger_config["type"] == "system_action"
