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


def test_requirement_activation_updates_linked_tasks_to_doing(client: TestClient):
    project_id = _create_project(client)
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"待激活需求-{uuid4().hex[:8]}"},
    )
    assert requirement.status_code == 200
    requirement_id = requirement.json()["id"]
    assert requirement.json()["status"] == "draft"

    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "requirement_id": requirement_id, "title": f"联动任务-{uuid4().hex[:8]}"},
    )
    assert task.status_code == 200
    task_id = task.json()["id"]
    assert task.json()["status"] == "todo"

    activated = client.post(f"/api/v1/requirements/{requirement_id}/activate")
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"

    task_detail = client.get(f"/api/v1/tasks/{task_id}")
    assert task_detail.status_code == 200
    assert task_detail.json()["status"] == "doing"

    history = client.get(f"/api/v1/requirements/{requirement_id}/status-operations")
    assert history.status_code == 200
    assert history.json()[-1]["action"] == "activate"
    assert history.json()[-1]["to_status"] == "active"


def test_requirement_close_requires_reason_and_records_history(client: TestClient):
    project_id = _create_project(client)
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"待关闭需求-{uuid4().hex[:8]}"},
    )
    assert requirement.status_code == 200
    requirement_id = requirement.json()["id"]

    activated = client.post(f"/api/v1/requirements/{requirement_id}/activate")
    assert activated.status_code == 200

    rejected = client.post(f"/api/v1/requirements/{requirement_id}/close", json={"remark": "缺少原因"})
    assert rejected.status_code == 422

    closed = client.post(
        f"/api/v1/requirements/{requirement_id}/close",
        json={"reason": "done", "remark": "已完成上线"},
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"

    history = client.get(f"/api/v1/requirements/{requirement_id}/status-operations")
    assert history.status_code == 200
    actions = [item["action"] for item in history.json()]
    assert actions[-2:] == ["activate", "close"]
    assert history.json()[-1]["reason"] == "done"
    assert history.json()[-1]["remark"] == "已完成上线"


def test_closed_requirement_can_be_reactivated_and_records_history(client: TestClient):
    project_id = _create_project(client)
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"重新激活需求-{uuid4().hex[:8]}"},
    )
    assert requirement.status_code == 200
    requirement_id = requirement.json()["id"]

    activated = client.post(f"/api/v1/requirements/{requirement_id}/activate")
    assert activated.status_code == 200
    closed = client.post(
        f"/api/v1/requirements/{requirement_id}/close",
        json={"reason": "延期", "remark": "暂时关闭"},
    )
    assert closed.status_code == 200

    reactivated = client.post(f"/api/v1/requirements/{requirement_id}/activate")
    assert reactivated.status_code == 200
    assert reactivated.json()["status"] == "active"

    history = client.get(f"/api/v1/requirements/{requirement_id}/status-operations")
    assert history.status_code == 200
    assert [item["action"] for item in history.json()][-3:] == ["activate", "close", "activate"]
    assert history.json()[-1]["from_status"] == "closed"
    assert history.json()[-1]["to_status"] == "active"


def test_requirement_status_cannot_be_changed_by_form_save(client: TestClient):
    project_id = _create_project(client)
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"表单状态保护-{uuid4().hex[:8]}", "status": "active"},
    )
    assert requirement.status_code == 200
    requirement_id = requirement.json()["id"]
    assert requirement.json()["status"] == "draft"

    updated = client.patch(f"/api/v1/requirements/{requirement_id}", json={"title": "表单更新标题", "status": "closed"})
    assert updated.status_code == 200
    assert updated.json()["title"] == "表单更新标题"
    assert updated.json()["status"] == "draft"


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
