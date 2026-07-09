from uuid import uuid4

from fastapi.testclient import TestClient


def test_workflow_handlers_are_exposed_as_backend_whitelist(client: TestClient):
    response = client.get("/api/v1/workflow-handlers")

    assert response.status_code == 200
    handler_keys = {item["handler_key"] for item in response.json()}
    assert "status_changed" in handler_keys
    assert "change_current_status" in handler_keys
    assert "batch_change_child_status" in handler_keys
    assert "block_operation" in handler_keys


def test_workflow_component_registry_crud(client: TestClient):
    suffix = uuid4().hex[:8]
    payload = {
        "component_key": f"custom_project_close_reason_{suffix}",
        "component_type": "action",
        "component_name": "Custom close requirement",
        "description": "Use backend handler whitelist",
        "object_type": "project",
        "handler_key": "batch_change_child_status",
        "config_schema": [
            {"field": "child_object", "label": "Child object", "type": "select", "options": [{"label": "Requirement", "value": "requirement"}]},
            {"field": "target_status", "label": "Target status", "type": "select", "options": [{"label": "Closed", "value": "closed"}]},
            {"field": "reason", "label": "Reason", "type": "text"},
        ],
        "enabled": True,
        "is_system": False,
        "sort_order": 88,
    }

    created = client.post("/api/v1/workflow-components", json=payload)
    assert created.status_code == 200
    created_data = created.json()
    assert created_data["component_key"] == payload["component_key"]
    assert created_data["handler_key"] == "batch_change_child_status"

    components = client.get("/api/v1/workflow-components")
    assert components.status_code == 200
    custom_component = next(item for item in components.json() if item["component_key"] == payload["component_key"])
    assert custom_component["component_type"] == "action"
    assert custom_component["component_name"] == payload["component_name"]

    updated = client.patch(
        f"/api/v1/workflow-components/{created_data['id']}",
        json={"component_name": "Custom close project requirement", "enabled": False},
    )
    assert updated.status_code == 200
    assert updated.json()["component_name"] == "Custom close project requirement"
    assert updated.json()["enabled"] is False

    disabled_components = client.get("/api/v1/workflow-components")
    disabled_component = next(item for item in disabled_components.json() if item["component_key"] == payload["component_key"])
    assert disabled_component["enabled"] is False
    assert client.delete(f"/api/v1/workflow-components/{created_data['id']}").status_code == 204


def test_workflow_component_rejects_unknown_handler(client: TestClient):
    response = client.post(
        "/api/v1/workflow-components",
        json={
            "component_key": f"invalid_handler_{uuid4().hex[:8]}",
            "component_type": "action",
            "component_name": "Invalid handler",
            "description": "should fail",
            "handler_key": "run_arbitrary_python",
            "config_schema": [],
        },
    )

    assert response.status_code == 400
    assert "handler" in response.json()["detail"]
