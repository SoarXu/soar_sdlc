from uuid import uuid4

from app.db.session import SessionLocal
from app.models.audit_log import AuditLog


def _create_requirement_with_task_tree(client):
    project = client.post("/api/v1/projects", json={"name": f"删除关联项目-{uuid4().hex[:8]}"})
    assert project.status_code == 200, project.text
    project_id = project.json()["id"]
    iteration = client.post(
        "/api/v1/iterations",
        json={"name": f"删除关联迭代-{uuid4().hex[:8]}", "project_ids": [project_id]},
    )
    assert iteration.status_code == 200, iteration.text
    requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project_id,
            "iteration_id": iteration.json()["id"],
            "title": "不应解除任务关联的需求",
        },
    )
    assert requirement.status_code == 200, requirement.text
    parent = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "requirement_id": requirement.json()["id"],
            "title": "关联根任务",
        },
    )
    assert parent.status_code == 200, parent.text
    child = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "parent_task_id": parent.json()["id"],
            "title": "关联子任务",
        },
    )
    assert child.status_code == 200, child.text
    return requirement.json(), parent.json(), child.json()


def test_delete_requirement_with_active_linked_task_tree_is_rejected_without_side_effects(client):
    requirement, parent, child = _create_requirement_with_task_tree(client)

    response = client.delete(f"/api/v1/requirements/{requirement['id']}")

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "REQUIREMENT_HAS_LINKED_TASKS",
        "message": "该需求已关联任务，请先处理关联任务后再删除。",
        "linked_task_count": 2,
    }
    assert client.get(f"/api/v1/requirements/{requirement['id']}").status_code == 200
    assert client.get(f"/api/v1/tasks/{parent['id']}").json()["requirement_id"] == requirement["id"]
    assert client.get(f"/api/v1/tasks/{child['id']}").json()["requirement_id"] == requirement["id"]
    with SessionLocal() as db:
        assert (
            db.query(AuditLog)
            .filter(AuditLog.object_type == "task", AuditLog.object_id.in_([parent["id"], child["id"]]))
            .count()
            == 0
        )


def test_deleted_linked_tasks_do_not_block_requirement_delete(client):
    requirement, parent, child = _create_requirement_with_task_tree(client)
    deleted_child = client.delete(f"/api/v1/tasks/{child['id']}")
    assert deleted_child.status_code == 204
    deleted_task = client.delete(f"/api/v1/tasks/{parent['id']}")
    assert deleted_task.status_code == 204

    deleted_requirement = client.delete(f"/api/v1/requirements/{requirement['id']}")

    assert deleted_requirement.status_code == 204
