from uuid import uuid4

from fastapi.testclient import TestClient


def _create_active_project(client: TestClient) -> int:
    project = client.post("/api/v1/projects", json={"name": f"Workflow Project {uuid4().hex[:8]}"})
    assert project.status_code == 200
    project_id = project.json()["id"]
    started = client.post(
        f"/api/v1/projects/{project_id}/start",
        json={"effective_time": "2026-06-01T09:00:00"},
    )
    assert started.status_code == 200
    return project_id


def _create_active_requirement_with_task(client: TestClient, project_id: int) -> tuple[int, int]:
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"Workflow Requirement {uuid4().hex[:8]}"},
    )
    assert requirement.status_code == 200
    requirement_id = requirement.json()["id"]
    activated_requirement = client.post(f"/api/v1/requirements/{requirement_id}/activate")
    assert activated_requirement.status_code == 200

    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "requirement_id": requirement_id, "title": f"Workflow Task {uuid4().hex[:8]}"},
    )
    assert task.status_code == 200
    task_id = task.json()["id"]
    activated_task = client.post(f"/api/v1/tasks/{task_id}/activate")
    assert activated_task.status_code == 200
    return requirement_id, task_id


def _create_workflow_rule(
    client: TestClient,
    nodes: list[dict],
    edges: list[dict],
    priority: int = 10,
    target_object: str = "project",
    trigger_action: str = "status_changed",
) -> int:
    payload = {
        "rule_name": f"Workflow Engine Rule {uuid4().hex[:8]}",
        "scope_type": "system",
        "target_object": target_object,
        "trigger_action": trigger_action,
        "condition_json": {"designer_version": 1, "nodes": nodes, "edges": edges},
        "action_json": {"trigger": {"target_object": target_object, "trigger_action": trigger_action}, "steps": []},
        "enabled": True,
        "priority": priority,
    }
    response = client.post("/api/v1/workflow-rules", json=payload)
    assert response.status_code == 200
    return response.json()["id"]


def test_project_close_workflow_changes_requirement_and_task_with_configured_reason(client: TestClient):
    project_id = _create_active_project(client)
    requirement_id, task_id = _create_active_requirement_with_task(client, project_id)
    nodes = [
        {
            "id": "node-1",
            "component_key": "project_status_changed",
            "category": "trigger",
            "label": "项目关闭",
            "x": 80,
            "y": 80,
            "config": {"to_status": "closed"},
        },
        {
            "id": "node-2",
            "component_key": "child_unclosed_exists",
            "category": "condition",
            "label": "存在未关闭需求",
            "x": 340,
            "y": 80,
            "config": {"child_object": "requirement", "status_not_in": ["closed"]},
        },
        {
            "id": "node-3",
            "component_key": "batch_change_child_status",
            "category": "action",
            "label": "关闭需求",
            "x": 600,
            "y": 80,
            "config": {"child_object": "requirement", "target_status": "closed", "reason": "工作流关闭"},
        },
        {
            "id": "node-4",
            "component_key": "batch_change_child_status",
            "category": "action",
            "label": "关闭任务",
            "x": 860,
            "y": 80,
            "config": {"child_object": "task", "target_status": "closed", "reason": "工作流关闭"},
        },
    ]
    _create_workflow_rule(
        client,
        nodes,
        [
            {"id": "edge-1", "source": "node-1", "target": "node-2"},
            {"id": "edge-2", "source": "node-2", "target": "node-3"},
            {"id": "edge-3", "source": "node-3", "target": "node-4"},
        ],
    )

    closed = client.post(
        f"/api/v1/projects/{project_id}/close",
        json={"effective_time": "2026-06-10T18:00:00", "remark": "close by workflow"},
    )

    assert closed.status_code == 200
    assert client.get(f"/api/v1/requirements/{requirement_id}").json()["status"] == "closed"
    assert client.get(f"/api/v1/tasks/{task_id}").json()["status"] == "closed"
    requirement_history = client.get(f"/api/v1/requirements/{requirement_id}/status-operations").json()
    task_history = client.get(f"/api/v1/tasks/{task_id}/status-operations").json()
    requirement_close = next(item for item in requirement_history if item["action"] == "close")
    task_close = next(item for item in task_history if item["action"] == "close")
    assert requirement_close["reason"] == "工作流关闭"
    assert task_close["reason"] == "工作流关闭"


def test_project_close_workflow_can_block_operation(client: TestClient):
    project_id = _create_active_project(client)
    nodes = [
        {
            "id": "node-1",
            "component_key": "project_status_changed",
            "category": "trigger",
            "label": "项目关闭",
            "x": 80,
            "y": 80,
            "config": {"to_status": "closed"},
        },
        {
            "id": "node-2",
            "component_key": "block_operation",
            "category": "action",
            "label": "阻断关闭",
            "x": 340,
            "y": 80,
            "config": {"message": "工作流阻断项目关闭"},
        },
    ]
    _create_workflow_rule(client, nodes, [{"id": "edge-1", "source": "node-1", "target": "node-2"}])

    blocked = client.post(
        f"/api/v1/projects/{project_id}/close",
        json={"effective_time": "2026-06-10T18:00:00"},
    )

    assert blocked.status_code == 400
    assert blocked.json()["detail"] == "工作流阻断项目关闭"
    assert client.get(f"/api/v1/projects/{project_id}").json()["status"] == "active"


def test_project_close_workflow_executes_custom_component_by_handler_key(client: TestClient):
    project_id = _create_active_project(client)
    requirement_id, _task_id = _create_active_requirement_with_task(client, project_id)
    nodes = [
        {
            "id": "node-1",
            "component_key": "project_status_changed",
            "handler_key": "status_changed",
            "category": "trigger",
            "label": "项目关闭",
            "x": 80,
            "y": 80,
            "config": {"to_status": "closed"},
        },
        {
            "id": "node-2",
            "component_key": "custom_close_requirements",
            "handler_key": "batch_change_child_status",
            "category": "action",
            "label": "自定义关闭需求",
            "x": 340,
            "y": 80,
            "config": {"child_object": "requirement", "target_status": "closed", "reason": "自定义组件关闭"},
        },
    ]
    _create_workflow_rule(client, nodes, [{"id": "edge-1", "source": "node-1", "target": "node-2"}])

    closed = client.post(
        f"/api/v1/projects/{project_id}/close",
        json={"effective_time": "2026-06-10T18:00:00"},
    )

    assert closed.status_code == 200
    assert client.get(f"/api/v1/requirements/{requirement_id}").json()["status"] == "closed"
    requirement_history = client.get(f"/api/v1/requirements/{requirement_id}/status-operations").json()
    requirement_close = next(item for item in requirement_history if item["action"] == "close")
    assert requirement_close["reason"] == "自定义组件关闭"
def test_workflow_can_change_current_requirement_status(client: TestClient):
    project_id = _create_active_project(client)
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"Current Status Requirement {uuid4().hex[:8]}"},
    )
    assert requirement.status_code == 200
    requirement_id = requirement.json()["id"]
    nodes = [
        {
            "id": "node-1",
            "component_key": "requirement_status_changed",
            "category": "trigger",
            "label": "requirement activated",
            "x": 80,
            "y": 80,
            "config": {"to_status": "active"},
        },
        {
            "id": "node-2",
            "component_key": "change_current_status",
            "category": "action",
            "label": "close current requirement",
            "x": 340,
            "y": 80,
            "config": {"target_status": "closed", "reason": "workflow changed current"},
        },
    ]
    _create_workflow_rule(
        client,
        nodes,
        [{"id": "edge-1", "source": "node-1", "target": "node-2"}],
        target_object="requirement",
    )

    activated = client.post(f"/api/v1/requirements/{requirement_id}/activate")

    assert activated.status_code == 200
    assert activated.json()["status"] == "closed"
    history = client.get(f"/api/v1/requirements/{requirement_id}/status-operations").json()
    workflow_change = next(item for item in history if item["action"] == "workflow_change_status")
    assert workflow_change["from_status"] == "active"
    assert workflow_change["to_status"] == "closed"
    assert workflow_change["reason"] == "workflow changed current"
