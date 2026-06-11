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


def test_requirement_update_records_only_changed_fields(client: TestClient):
    project_id = _create_project(client)
    requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project_id,
            "title": f"编辑记录需求-{uuid4().hex[:8]}",
            "priority": "3",
            "description": "原描述",
        },
    ).json()

    updated = client.patch(
        f"/api/v1/requirements/{requirement['id']}",
        json={"title": "编辑后需求", "priority": "2", "description": "原描述"},
    )
    assert updated.status_code == 200

    logs = client.get(f"/api/v1/requirements/{requirement['id']}/audit-logs")
    assert logs.status_code == 200
    data = logs.json()
    assert len(data) == 1
    assert data[0]["action"] == "update"
    assert data[0]["object_type"] == "requirement"
    assert data[0]["object_id"] == requirement["id"]
    assert data[0]["before_data"] == {"title": requirement["title"], "priority": "3"}
    assert data[0]["after_data"] == {"title": "编辑后需求", "priority": "2"}

    unchanged = client.patch(f"/api/v1/requirements/{requirement['id']}", json={"title": "编辑后需求"})
    assert unchanged.status_code == 200
    assert len(client.get(f"/api/v1/requirements/{requirement['id']}/audit-logs").json()) == 1


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


def test_task_can_be_activated_and_closed_with_history(client: TestClient):
    project_id = _create_project(client)
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "title": f"任务状态流转-{uuid4().hex[:8]}"},
    )
    assert task.status_code == 200
    task_id = task.json()["id"]

    activated = client.post(f"/api/v1/tasks/{task_id}/activate")
    assert activated.status_code == 200
    assert activated.json()["status"] == "doing"

    rejected = client.post(f"/api/v1/tasks/{task_id}/close", json={"remark": "缺少原因"})
    assert rejected.status_code == 422

    closed = client.post(
        f"/api/v1/tasks/{task_id}/close",
        json={"reason": "不做", "remark": "任务取消"},
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"

    history = client.get(f"/api/v1/tasks/{task_id}/status-operations")
    assert history.status_code == 200
    assert [item["action"] for item in history.json()][-2:] == ["activate", "close"]
    assert history.json()[-1]["reason"] == "不做"
    assert history.json()[-1]["remark"] == "任务取消"


def test_task_update_records_only_changed_fields(client: TestClient):
    project_id = _create_project(client)
    task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "title": f"任务编辑记录-{uuid4().hex[:8]}",
            "description": "原描述",
            "priority": "medium",
        },
    ).json()

    updated = client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"title": "任务编辑后标题", "description": "原描述", "priority": "high"},
    )
    assert updated.status_code == 200

    logs = client.get(f"/api/v1/tasks/{task['id']}/audit-logs")
    assert logs.status_code == 200
    data = logs.json()
    assert len(data) == 1
    assert data[0]["action"] == "update"
    assert data[0]["object_type"] == "task"
    assert data[0]["object_id"] == task["id"]
    assert data[0]["before_data"] == {"title": task["title"], "priority": "medium"}
    assert data[0]["after_data"] == {"title": "任务编辑后标题", "priority": "high"}

    unchanged = client.patch(f"/api/v1/tasks/{task['id']}", json={"title": "任务编辑后标题"})
    assert unchanged.status_code == 200
    assert len(client.get(f"/api/v1/tasks/{task['id']}/audit-logs").json()) == 1


def test_requirement_close_closes_open_linked_tasks_with_same_reason(client: TestClient):
    project_id = _create_project(client)
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"关闭级联需求-{uuid4().hex[:8]}"},
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "requirement_id": requirement["id"], "title": f"关闭级联任务-{uuid4().hex[:8]}"},
    ).json()
    client.post(f"/api/v1/tasks/{task['id']}/activate")

    closed = client.post(
        f"/api/v1/requirements/{requirement['id']}/close",
        json={"reason": "延期", "remark": "需求延期关闭"},
    )

    assert closed.status_code == 200
    assert client.get(f"/api/v1/tasks/{task['id']}").json()["status"] == "closed"
    task_history = client.get(f"/api/v1/tasks/{task['id']}/status-operations").json()
    assert task_history[-1]["action"] == "close"
    assert task_history[-1]["reason"] == "延期"
    assert task_history[-1]["remark"] == "需求延期关闭"


def test_closed_project_blocks_requirement_and_task_activation(client: TestClient):
    project_id = _create_project(client)
    client.post(f"/api/v1/projects/{project_id}/start", json={"effective_time": "2026-06-01T09:00:00"})
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"项目关闭需求-{uuid4().hex[:8]}"},
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "requirement_id": requirement["id"], "title": f"项目关闭任务-{uuid4().hex[:8]}"},
    ).json()
    client.post(f"/api/v1/requirements/{requirement['id']}/activate")
    client.post(f"/api/v1/tasks/{task['id']}/activate")

    closed_project = client.post(f"/api/v1/projects/{project_id}/close", json={"effective_time": "2026-06-10T18:00:00"})
    assert closed_project.status_code == 200

    requirement_detail = client.get(f"/api/v1/requirements/{requirement['id']}")
    task_detail = client.get(f"/api/v1/tasks/{task['id']}")
    assert requirement_detail.json()["status"] == "closed"
    assert task_detail.json()["status"] == "closed"

    requirement_history = client.get(f"/api/v1/requirements/{requirement['id']}/status-operations").json()
    task_history = client.get(f"/api/v1/tasks/{task['id']}/status-operations").json()
    assert requirement_history[-1]["action"] == "close"
    assert requirement_history[-1]["reason"] == "不做"
    assert task_history[-1]["action"] == "close"
    assert task_history[-1]["reason"] == "不做"

    requirement_reactivate = client.post(f"/api/v1/requirements/{requirement['id']}/activate")
    task_reactivate = client.post(f"/api/v1/tasks/{task['id']}/activate")
    assert requirement_reactivate.status_code == 400
    assert requirement_reactivate.json()["detail"] == "项目已关闭，需求不允许激活"
    assert task_reactivate.status_code == 400
    assert task_reactivate.json()["detail"] == "项目已关闭，任务不允许激活"


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
