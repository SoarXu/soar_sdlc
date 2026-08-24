from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import SessionLocal
from app.models.workflow_definition import WorkflowState
from app.models.work_item_iteration_history import WorkItemIterationHistory


def _create_project(client: TestClient, name: str) -> int:
    response = client.post("/api/v1/projects", json={"name": name})
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _create_iteration(client: TestClient, project_id: int, name: str) -> int:
    response = client.post("/api/v1/iterations", json={"name": name, "project_ids": [project_id]})
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _create_task_tree(
    client: TestClient, project_id: int, iteration_id: int, *, with_requirement: bool = True
) -> tuple[dict | None, dict, dict, dict]:
    requirement = None
    if with_requirement:
        requirement_response = client.post(
            "/api/v1/requirements",
            json={"project_id": project_id, "iteration_id": iteration_id, "title": f"Task tree requirement {uuid4().hex[:8]}"},
        )
        assert requirement_response.status_code == 200, requirement_response.text
        requirement = requirement_response.json()
    root = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "requirement_id": requirement["id"] if requirement else None, "title": "Root task"},
    )
    assert root.status_code == 200, root.text
    root = root.json()
    child = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "parent_task_id": root["id"], "title": "Child task"},
    )
    assert child.status_code == 200, child.text
    child = child.json()
    grandchild = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "parent_task_id": child["id"], "title": "Grandchild task"},
    )
    assert grandchild.status_code == 200, grandchild.text
    return requirement, root, child, grandchild.json()


def _task_scope(client: TestClient, task_id: int) -> dict:
    task = client.get(f"/api/v1/tasks/{task_id}")
    assert task.status_code == 200, task.text
    return task.json()


def test_root_task_iteration_move_updates_the_entire_tree_and_history(client: TestClient):
    project_id = _create_project(client, f"Tree move project {uuid4().hex[:8]}")
    source_iteration_id = _create_iteration(client, project_id, "Source iteration")
    target_iteration_id = _create_iteration(client, project_id, "Target iteration")
    _requirement, root, child, grandchild = _create_task_tree(
        client, project_id, source_iteration_id, with_requirement=False
    )

    moved = client.patch(f"/api/v1/tasks/{root['id']}", json={"iteration_id": target_iteration_id})

    assert moved.status_code == 200, moved.text
    for task_id in (root["id"], child["id"], grandchild["id"]):
        assert _task_scope(client, task_id)["iteration_id"] == target_iteration_id
        with SessionLocal() as db:
            history = (
                db.query(WorkItemIterationHistory)
                .filter(WorkItemIterationHistory.object_type == "task", WorkItemIterationHistory.object_id == task_id)
                .order_by(WorkItemIterationHistory.id.asc())
                .all()
            )
            assert history[-2].iteration_id == source_iteration_id
            assert history[-2].left_at is not None
            assert history[-1].iteration_id == target_iteration_id
            assert history[-1].left_at is None


def test_child_task_scope_cannot_be_changed_directly(client: TestClient):
    project_id = _create_project(client, f"Child scope project {uuid4().hex[:8]}")
    source_iteration_id = _create_iteration(client, project_id, "Source iteration")
    target_iteration_id = _create_iteration(client, project_id, "Target iteration")
    _requirement, _root, child, _grandchild = _create_task_tree(client, project_id, source_iteration_id)

    response = client.patch(f"/api/v1/tasks/{child['id']}", json={"iteration_id": target_iteration_id})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "CHILD_TASK_SCOPE_IMMUTABLE"
    assert _task_scope(client, child["id"])["iteration_id"] == source_iteration_id


def test_child_task_cannot_be_linked_to_an_iteration_independently(client: TestClient):
    project_id = _create_project(client, f"Child iteration link project {uuid4().hex[:8]}")
    source_iteration_id = _create_iteration(client, project_id, "Source iteration")
    target_iteration_id = _create_iteration(client, project_id, "Target iteration")
    _requirement, root, child, grandchild = _create_task_tree(
        client, project_id, source_iteration_id, with_requirement=False
    )
    before = {task_id: _task_scope(client, task_id)["iteration_id"] for task_id in (root["id"], child["id"], grandchild["id"])}

    response = client.post(
        f"/api/v1/iterations/{target_iteration_id}/tasks",
        json={"task_ids": [child["id"]]},
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"] == {
        "code": "CHILD_TASK_SCOPE_IMMUTABLE",
        "message": "子任务的项目、需求和迭代由父任务统一管理。",
    }
    for task_id, iteration_id in before.items():
        assert _task_scope(client, task_id)["iteration_id"] == iteration_id


def test_requirement_project_and_iteration_move_updates_every_task_in_the_tree(client: TestClient):
    source_project_id = _create_project(client, f"Tree source project {uuid4().hex[:8]}")
    source_iteration_id = _create_iteration(client, source_project_id, "Source iteration")
    target_project_id = _create_project(client, f"Tree target project {uuid4().hex[:8]}")
    target_iteration_id = _create_iteration(client, target_project_id, "Target iteration")
    requirement, root, child, grandchild = _create_task_tree(client, source_project_id, source_iteration_id)

    moved = client.patch(
        f"/api/v1/requirements/{requirement['id']}",
        json={"project_id": target_project_id, "iteration_id": target_iteration_id},
    )

    assert moved.status_code == 200, moved.text
    assert moved.json()["project_id"] == target_project_id
    assert moved.json()["iteration_id"] == target_iteration_id
    for task_id in (root["id"], child["id"], grandchild["id"]):
        task = _task_scope(client, task_id)
        assert task["project_id"] == target_project_id
        assert task["requirement_id"] == requirement["id"]
        assert task["iteration_id"] == target_iteration_id


def test_terminal_descendant_blocks_root_tree_move_before_any_history_or_scope_change(client: TestClient):
    project_id = _create_project(client, f"Tree terminal project {uuid4().hex[:8]}")
    source_iteration_id = _create_iteration(client, project_id, "Source iteration")
    target_iteration_id = _create_iteration(client, project_id, "Target iteration")
    _requirement, root, child, grandchild = _create_task_tree(
        client, project_id, source_iteration_id, with_requirement=False
    )
    with SessionLocal() as db:
        terminal_state = (
            db.query(WorkflowState)
            .filter(
                WorkflowState.definition_id == child["workflow_definition_id"],
                WorkflowState.category == "terminal",
                WorkflowState.enabled.is_(True),
            )
            .first()
        )
        assert terminal_state is not None
        db.execute(
            text("UPDATE tasks SET current_state_id = :state_id WHERE id = :task_id"),
            {"state_id": terminal_state.id, "task_id": grandchild["id"]},
        )
        db.commit()
        history_count = db.query(WorkItemIterationHistory).filter(
            WorkItemIterationHistory.object_type == "task",
            WorkItemIterationHistory.object_id.in_([root["id"], child["id"], grandchild["id"]]),
        ).count()

    response = client.patch(f"/api/v1/tasks/{root['id']}", json={"iteration_id": target_iteration_id})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "TASK_TREE_MOVE_BLOCKED"
    for task_id in (root["id"], child["id"], grandchild["id"]):
        assert _task_scope(client, task_id)["iteration_id"] == source_iteration_id
    with SessionLocal() as db:
        assert db.query(WorkItemIterationHistory).filter(
            WorkItemIterationHistory.object_type == "task",
            WorkItemIterationHistory.object_id.in_([root["id"], child["id"], grandchild["id"]]),
        ).count() == history_count
