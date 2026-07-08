from uuid import uuid4

from fastapi.testclient import TestClient


def test_assignee_rule_config_crud_and_project_binding(client: TestClient):
    response = client.get("/api/v1/assignee-rule-configs")
    assert response.status_code == 200
    assert len(response.json()) >= 1
    default_config = response.json()[0]
    assert "责任人" not in default_config["name"]
    assert default_config["requirement_owner_roles"] == ""
    assert default_config["task_owner_roles"] == ""
    assert default_config["bug_owner_roles"] == ""

    name = f"规则配置-{uuid4().hex[:8]}"
    created = client.post(
        "/api/v1/assignee-rule-configs",
        json={
            "name": name,
            "description": "custom rules",
            "requirement_owner_roles": "tester",
            "task_owner_roles": "product_manager",
            "test_case_tester_roles": "tester",
            "test_run_owner_roles": "test_lead",
            "bug_owner_roles": "development_lead",
        },
    )
    assert created.status_code == 201
    config = created.json()
    assert config["name"] == name
    assert config["requirement_owner_roles"] == "tester"

    project = client.post(
        "/api/v1/projects",
        json={"name": f"Rule Bound Project-{uuid4().hex[:8]}", "assignee_rule_config_id": config["id"]},
    )
    assert project.status_code == 200
    assert project.json()["assignee_rule_config_id"] == config["id"]

    updated = client.patch(
        f"/api/v1/assignee-rule-configs/{config['id']}",
        json={"task_owner_roles": "developer", "enabled": False},
    )
    assert updated.status_code == 200
    assert updated.json()["task_owner_roles"] == "developer"
    assert updated.json()["enabled"] is False

    deleted = client.delete(f"/api/v1/assignee-rule-configs/{config['id']}")
    assert deleted.status_code == 204
