from uuid import uuid4

from fastapi.testclient import TestClient


def test_workflow_components_and_templates(client: TestClient):
    components = client.get("/api/v1/workflow-rules/components")
    assert components.status_code == 200
    component_keys = {item["component_key"] for item in components.json()}
    assert "project_status_changed" in component_keys
    assert "child_unclosed_exists" in component_keys
    assert "batch_change_child_status" in component_keys

    templates = client.get("/api/v1/workflow-rules/templates")
    assert templates.status_code == 200
    project_close = next(item for item in templates.json() if item["template_key"] == "project_close_requirements")
    assert project_close["target_object"] == "project"
    assert project_close["trigger_action"] == "status_changed"
    assert len(project_close["condition_json"]["nodes"]) >= 3


def test_workflow_rule_crud_persists_canvas(client: TestClient):
    suffix = uuid4().hex[:8]
    payload = {
        "rule_name": f"Project close rule {suffix}",
        "scope_type": "system",
        "scope_id": None,
        "target_object": "project",
        "trigger_action": "status_changed",
        "condition_json": {
            "designer_version": 1,
            "nodes": [
                {
                    "id": "node-1",
                    "component_key": "project_status_changed",
                    "category": "trigger",
                    "label": "项目状态变更",
                    "x": 80,
                    "y": 80,
                    "config": {"to_status": "closed"},
                }
            ],
            "edges": [],
        },
        "action_json": {"trigger": {"target_object": "project", "trigger_action": "status_changed"}, "steps": []},
        "enabled": True,
        "priority": 100,
        "description": "created by api test",
    }
    created = client.post("/api/v1/workflow-rules", json=payload)
    assert created.status_code == 200
    data = created.json()
    assert data["rule_name"] == payload["rule_name"]
    assert data["condition_json"]["nodes"][0]["component_key"] == "project_status_changed"

    listed = client.get("/api/v1/workflow-rules")
    assert listed.status_code == 200
    assert any(item["id"] == data["id"] for item in listed.json())

    updated = client.patch(
        f"/api/v1/workflow-rules/{data['id']}",
        json={"enabled": False, "priority": 50, "block_message": "blocked by workflow"},
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False
    assert updated.json()["priority"] == 50
    assert updated.json()["block_message"] == "blocked by workflow"

    deleted = client.delete(f"/api/v1/workflow-rules/{data['id']}")
    assert deleted.status_code == 204
