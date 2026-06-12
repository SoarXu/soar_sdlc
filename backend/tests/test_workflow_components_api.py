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


def test_workflow_component_registry_crud_and_designer_source(client: TestClient):
    suffix = uuid4().hex[:8]
    payload = {
        "component_key": f"custom_project_close_reason_{suffix}",
        "component_type": "action",
        "component_name": "自定义关闭需求",
        "description": "使用后端白名单 handler 批量关闭项目下需求",
        "object_type": "project",
        "handler_key": "batch_change_child_status",
        "config_schema": [
            {"field": "child_object", "label": "子对象", "type": "select", "options": [{"label": "需求", "value": "requirement"}]},
            {"field": "target_status", "label": "目标状态", "type": "select", "options": [{"label": "已关闭", "value": "closed"}]},
            {"field": "reason", "label": "原因", "type": "text"},
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
    assert any(item["component_key"] == payload["component_key"] for item in components.json())

    designer_components = client.get("/api/v1/workflow-rules/components")
    assert designer_components.status_code == 200
    custom_component = next(item for item in designer_components.json() if item["component_key"] == payload["component_key"])
    assert custom_component["category"] == "action"
    assert custom_component["label"] == "自定义关闭需求"

    updated = client.patch(
        f"/api/v1/workflow-components/{created_data['id']}",
        json={"component_name": "自定义关闭项目需求", "enabled": False},
    )
    assert updated.status_code == 200
    assert updated.json()["component_name"] == "自定义关闭项目需求"
    assert updated.json()["enabled"] is False

    designer_components = client.get("/api/v1/workflow-rules/components")
    assert all(item["component_key"] != payload["component_key"] for item in designer_components.json())

    deleted = client.delete(f"/api/v1/workflow-components/{created_data['id']}")
    assert deleted.status_code == 204


def test_workflow_component_rejects_unknown_handler(client: TestClient):
    response = client.post(
        "/api/v1/workflow-components",
        json={
            "component_key": f"invalid_handler_{uuid4().hex[:8]}",
            "component_type": "action",
            "component_name": "非法 handler",
            "description": "should fail",
            "handler_key": "run_arbitrary_python",
            "config_schema": [],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "未知的工作流 handler"
