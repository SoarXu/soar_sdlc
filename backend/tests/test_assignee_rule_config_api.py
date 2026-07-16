from uuid import uuid4

from fastapi.testclient import TestClient


def _create_draft_config(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/assignee-rule-configs",
        json={
            "name": f"工作流方案-{uuid4().hex[:8]}",
            "description": "lifecycle test",
            "requirement_owner_roles": "tester",
            "task_owner_roles": "product_manager",
            "test_case_tester_roles": "tester",
            "test_run_owner_roles": "test_lead",
            "bug_owner_roles": "development_lead",
        },
    )
    assert response.status_code == 201
    return response.json()


def _configure_core_workflows(client: TestClient, config_id: int) -> None:
    for object_type in ("requirement", "task", "bug"):
        definition = client.post(
            "/api/v1/workflow-definitions",
            json={
                "name": f"{object_type}-{config_id}",
                "object_type": object_type,
                "scope_type": "assignee_rule_config",
                "scope_id": config_id,
            },
        )
        assert definition.status_code == 201
        applied = client.post(f"/api/v1/workflow-definitions/{definition.json()['id']}/apply-template")
        assert applied.status_code == 200


def test_workflow_scheme_lifecycle_guards_project_binding_and_disable(client: TestClient):
    config = _create_draft_config(client)
    assert config["lifecycle_status"] == "draft"

    draft_binding = client.post(
        "/api/v1/projects",
        json={"name": f"Draft Scheme Project-{uuid4().hex[:8]}", "assignee_rule_config_id": config["id"]},
    )
    assert draft_binding.status_code == 409

    invalid_enable = client.post(f"/api/v1/assignee-rule-configs/{config['id']}/enable")
    assert invalid_enable.status_code == 422
    assert set(invalid_enable.json()["detail"]["invalid_object_types"]) == {"requirement", "task", "bug"}

    _configure_core_workflows(client, config["id"])
    enabled = client.post(f"/api/v1/assignee-rule-configs/{config['id']}/enable")
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["lifecycle_status"] == "enabled"

    project = client.post(
        "/api/v1/projects",
        json={"name": f"Enabled Scheme Project-{uuid4().hex[:8]}", "assignee_rule_config_id": config["id"]},
    )
    assert project.status_code == 200

    blocked = client.post(f"/api/v1/assignee-rule-configs/{config['id']}/disable")
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["project_count"] == 1
    assert blocked.json()["detail"]["projects_url"].endswith(f"assignee_rule_config_id={config['id']}")

    unbound = client.patch(f"/api/v1/projects/{project.json()['id']}", json={"assignee_rule_config_id": None})
    assert unbound.status_code == 200
    disabled = client.post(f"/api/v1/assignee-rule-configs/{config['id']}/disable")
    assert disabled.status_code == 200
    assert disabled.json()["lifecycle_status"] == "disabled"

    options = client.get("/api/v1/assignee-rule-configs/project-options")
    assert options.status_code == 200
    assert config["id"] not in {item["id"] for item in options.json()}


def test_lifecycle_cannot_be_mutated_through_generic_patch(client: TestClient):
    config = _create_draft_config(client)

    response = client.patch(
        f"/api/v1/assignee-rule-configs/{config['id']}",
        json={"lifecycle_status": "enabled", "enabled": True},
    )

    assert response.status_code == 422
