from uuid import uuid4

from fastapi.testclient import TestClient


def _create_project(client: TestClient) -> int:
    response = client.post("/api/v1/projects", json={"name": f"项目-{uuid4().hex[:8]}"})
    assert response.status_code == 200
    return response.json()["id"]


def test_iteration_crud_persists_to_database(client: TestClient):
    project_id = _create_project(client)

    created = client.post(
        "/api/v1/iterations",
        json={"project_id": project_id, "name": "MVP 迭代", "status": "planning", "goal": "完成主链路"},
    )
    assert created.status_code == 200
    iteration_id = created.json()["id"]
    assert created.json()["project_id"] == project_id

    updated = client.patch(f"/api/v1/iterations/{iteration_id}", json={"status": "active"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "active"

    deleted = client.delete(f"/api/v1/iterations/{iteration_id}")
    assert deleted.status_code == 204


def test_requirement_can_generate_task_without_review_by_default(client: TestClient):
    project_id = _create_project(client)
    requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project_id,
            "title": "需求生成任务",
            "priority": "1",
            "owner_id": 1,
            "review_status": "not_required",
        },
    )
    assert requirement.status_code == 200
    requirement_id = requirement.json()["id"]

    generated = client.post(
        f"/api/v1/requirements/{requirement_id}/generate-task",
        json={"title": "实现需求生成任务", "task_type": "development"},
    )
    assert generated.status_code == 200
    data = generated.json()
    assert data["requirement_id"] == requirement_id
    assert data["project_id"] == project_id
    assert data["owner_id"] == 1
    assert data["source_requirement_review_status"] == "not_required"


def test_requirement_and_task_crud_use_prd_fields(client: TestClient):
    project_id = _create_project(client)

    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": "需求 CRUD", "priority": "3", "status": "draft"},
    )
    assert requirement.status_code == 200
    requirement_id = requirement.json()["id"]
    assert requirement.json()["priority"] == "3"

    default_priority_requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"默认优先级-{uuid4().hex[:8]}"},
    )
    assert default_priority_requirement.status_code == 200
    assert default_priority_requirement.json()["priority"] == "3"

    requirement_update = client.patch(f"/api/v1/requirements/{requirement_id}", json={"status": "active"})
    assert requirement_update.status_code == 200
    assert requirement_update.json()["status"] == "active"

    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "requirement_id": requirement_id, "title": "任务 CRUD"},
    )
    assert task.status_code == 200
    task_id = task.json()["id"]
    assert task.json()["requirement_id"] == requirement_id

    task_update = client.patch(f"/api/v1/tasks/{task_id}", json={"status": "doing", "actual_hours": 1.5})
    assert task_update.status_code == 200
    assert task_update.json()["status"] == "doing"
    assert task_update.json()["actual_hours"] == 1.5

    assert client.delete(f"/api/v1/tasks/{task_id}").status_code == 204
    assert client.delete(f"/api/v1/requirements/{requirement_id}").status_code == 204


def test_requirement_and_task_detail_endpoints(client: TestClient):
    project_id = _create_project(client)
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"详情需求-{uuid4().hex[:8]}", "description": "需求详情描述"},
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "requirement_id": requirement["id"], "title": f"详情任务-{uuid4().hex[:8]}"},
    ).json()

    requirement_detail = client.get(f"/api/v1/requirements/{requirement['id']}")
    task_detail = client.get(f"/api/v1/tasks/{task['id']}")

    assert requirement_detail.status_code == 200
    assert requirement_detail.json()["id"] == requirement["id"]
    assert requirement_detail.json()["title"] == requirement["title"]
    assert task_detail.status_code == 200
    assert task_detail.json()["id"] == task["id"]
    assert task_detail.json()["requirement_id"] == requirement["id"]
