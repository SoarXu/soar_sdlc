from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.models.workflow_definition import WorkflowState


def _create_project(client: TestClient, name: str) -> int:
    response = client.post("/api/v1/projects", json={"name": name})
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _create_iteration(client: TestClient, project_id: int) -> int:
    response = client.post(
        "/api/v1/iterations",
        json={"name": f"Task hierarchy iteration {uuid4().hex[:8]}", "project_ids": [project_id]},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _create_requirement(client: TestClient, project_id: int, iteration_id: int) -> dict:
    response = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
            "title": f"Task hierarchy requirement {uuid4().hex[:8]}",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_child_task_inherits_parent_scope_and_task_detail_exposes_hierarchy_metadata(client: TestClient):
    parent_project_id = _create_project(client, f"Task hierarchy parent {uuid4().hex[:8]}")
    parent_iteration_id = _create_iteration(client, parent_project_id)
    parent_requirement = _create_requirement(client, parent_project_id, parent_iteration_id)
    other_project_id = _create_project(client, f"Task hierarchy other {uuid4().hex[:8]}")
    other_iteration_id = _create_iteration(client, other_project_id)
    other_requirement = _create_requirement(client, other_project_id, other_iteration_id)
    parent = client.post(
        "/api/v1/tasks",
        json={
            "project_id": parent_project_id,
            "requirement_id": parent_requirement["id"],
            "title": "Parent task",
        },
    )
    assert parent.status_code == 200, parent.text
    parent = parent.json()

    child = client.post(
        "/api/v1/tasks",
        json={
            "project_id": other_project_id,
            "requirement_id": other_requirement["id"],
            "iteration_id": other_iteration_id,
            "parent_task_id": parent["id"],
            "title": "Child task",
        },
    )
    assert child.status_code == 200, child.text
    child = child.json()
    detail = client.get(f"/api/v1/tasks/{parent['id']}")
    children = client.get(f"/api/v1/tasks/{parent['id']}/children?page=1&page_size=20")

    assert child["parent_task_id"] == parent["id"]
    assert child["project_id"] == parent_project_id
    assert child["requirement_id"] == parent_requirement["id"]
    assert child["iteration_id"] == parent_iteration_id
    assert detail.status_code == 200, detail.text
    assert detail.json()["direct_child_count"] == 1
    assert detail.json()["parent_task"] is None
    child_detail = client.get(f"/api/v1/tasks/{child['id']}")
    assert child_detail.json()["parent_task"] == {
        "id": parent["id"],
        "title": parent["title"],
        "status_name": parent["status_name"],
        "owner_id": parent["owner_id"],
    }
    assert children.status_code == 200, children.text
    assert children.json()["total"] == 1
    assert [item["id"] for item in children.json()["items"]] == [child["id"]]


def test_terminal_parent_rejects_child_creation_with_structured_conflict(client: TestClient):
    project_id = _create_project(client, f"Task hierarchy terminal {uuid4().hex[:8]}")
    parent = client.post("/api/v1/tasks", json={"project_id": project_id, "title": "Terminal parent"})
    assert parent.status_code == 200, parent.text
    parent = parent.json()
    with SessionLocal() as db:
        terminal_state = (
            db.query(WorkflowState)
            .filter(
                WorkflowState.definition_id == parent["workflow_definition_id"],
                WorkflowState.category == "terminal",
                WorkflowState.enabled.is_(True),
            )
            .first()
        )
        assert terminal_state is not None
        db.execute(
            __import__("sqlalchemy").text("UPDATE tasks SET current_state_id = :state_id WHERE id = :task_id"),
            {"state_id": terminal_state.id, "task_id": parent["id"]},
        )
        db.commit()

    response = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "parent_task_id": parent["id"], "title": "Rejected child"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "TASK_PARENT_TERMINAL"


def test_child_task_scope_is_immutable_and_parent_with_children_cannot_be_deleted(client: TestClient):
    project = client.post("/api/v1/projects", json={"name": f"Task hierarchy scope {uuid4().hex[:8]}"}).json()
    other_project = client.post("/api/v1/projects", json={"name": f"Task hierarchy other scope {uuid4().hex[:8]}"}).json()
    parent = client.post(
        "/api/v1/tasks", json={"project_id": project["id"], "title": "Parent task"}
    )
    assert parent.status_code == 200, parent.text
    parent = parent.json()
    child = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "parent_task_id": parent["id"], "title": "Child task"},
    )
    assert child.status_code == 200, child.text

    scope_change = client.patch(
        f"/api/v1/tasks/{child.json()['id']}", json={"project_id": other_project["id"]}
    )
    delete_parent = client.delete(f"/api/v1/tasks/{parent['id']}")

    assert scope_change.status_code == 409
    assert scope_change.json()["detail"] == {
        "code": "CHILD_TASK_SCOPE_IMMUTABLE",
        "message": "子任务的项目、需求和迭代由父任务统一管理。",
    }
    assert delete_parent.status_code == 409
    assert delete_parent.json()["detail"]["code"] == "TASK_HAS_ACTIVE_CHILDREN"
