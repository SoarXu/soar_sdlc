from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.session import SessionLocal


def _create_project(client: TestClient, name: str | None = None) -> int:
    response = client.post("/api/v1/projects", json={"name": name or f"Project-{uuid4().hex[:8]}"})
    assert response.status_code == 200
    return response.json()["id"]


def _create_iteration(client: TestClient, project_id: int, name: str | None = None) -> int:
    response = client.post(
        "/api/v1/iterations",
        json={"project_ids": [project_id], "name": name or f"Iteration-{uuid4().hex[:8]}"},
    )
    assert response.status_code == 200
    return response.json()["id"]


def test_workbench_groups_items_by_iteration_and_supports_test_case_iteration(client: TestClient):
    project_id = _create_project(client, "Workbench Project")
    iteration_id = _create_iteration(client, project_id, "Workbench Iteration")

    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": "Workbench Requirement"},
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": "Workbench Task"},
    ).json()
    test_case = client.post(
        "/api/v1/test-cases",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": "Workbench Case"},
    ).json()
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": "Workbench Bug"},
    ).json()

    response = client.get("/api/v1/dashboard/workbench")

    assert response.status_code == 200
    boards = response.json()["iterations"]
    board = next(item for item in boards if item["id"] == iteration_id)
    assert {item["id"] for item in board["requirements"]} == {requirement["id"]}
    assert {item["id"] for item in board["tasks"]} == {task["id"]}
    assert {item["id"] for item in board["test_cases"]} == {test_case["id"]}
    assert {item["id"] for item in board["bugs"]} == {bug["id"]}
    assert board["counts"] == {"requirements": 1, "tasks": 1, "test_cases": 1, "bugs": 1}


def test_workbench_move_updates_iteration_id_for_supported_objects(client: TestClient):
    project_id = _create_project(client, "Move Project")
    source_iteration = _create_iteration(client, project_id, "Source Iteration")
    target_iteration = _create_iteration(client, project_id, "Target Iteration")
    test_case = client.post(
        "/api/v1/test-cases",
        json={"project_id": project_id, "iteration_id": source_iteration, "title": "Movable Case"},
    ).json()

    moved = client.post(
        "/api/v1/dashboard/workbench/move",
        json={"object_type": "test_case", "object_id": test_case["id"], "target_iteration_id": target_iteration},
    )

    assert moved.status_code == 200
    assert moved.json()["iteration_id"] == target_iteration
    detail = client.get(f"/api/v1/test-cases/{test_case['id']}")
    assert detail.status_code == 200
    assert detail.json()["iteration_id"] == target_iteration


def test_workbench_move_rejects_items_outside_target_iteration_project_scope(client: TestClient):
    source_project = _create_project(client, "Source Project")
    target_project = _create_project(client, "Target Project")
    target_iteration = _create_iteration(client, target_project, "Target Iteration")
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": source_project, "title": "Out of scope requirement"},
    ).json()

    moved = client.post(
        "/api/v1/dashboard/workbench/move",
        json={"object_type": "requirement", "object_id": requirement["id"], "target_iteration_id": target_iteration},
    )

    assert moved.status_code == 400
    assert "项目范围" in moved.json()["detail"]


def test_workbench_only_shows_items_matching_iteration_lifecycle_phase(client: TestClient):
    project_id = _create_project(client, "Phase Project")
    iteration_id = _create_iteration(client, project_id, "Development Iteration")
    visible_requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
            "title": "Development requirement",
            "lifecycle_phase": "development",
        },
    ).json()
    hidden_requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
            "title": "Maintenance requirement",
            "lifecycle_phase": "maintenance",
        },
    ).json()
    db = SessionLocal()
    try:
        from sqlalchemy import text

        db.execute(text("update requirements set lifecycle_phase = 'maintenance' where id = :id"), {"id": hidden_requirement["id"]})
        db.commit()
    finally:
        db.close()

    response = client.get("/api/v1/dashboard/workbench")

    assert response.status_code == 200
    board = next(item for item in response.json()["iterations"] if item["id"] == iteration_id)
    requirement_ids = {item["id"] for item in board["requirements"]}
    assert visible_requirement["id"] in requirement_ids
    assert hidden_requirement["id"] not in requirement_ids


def test_requirement_and_task_can_be_completed_with_status_history(client: TestClient):
    project_id = _create_project(client, "Completion Project")
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": "Completable requirement"},
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "title": "Completable task"},
    ).json()

    completed_requirement = client.post(f"/api/v1/requirements/{requirement['id']}/complete")
    completed_task = client.post(f"/api/v1/tasks/{task['id']}/complete")

    assert completed_requirement.status_code == 200
    assert completed_requirement.json()["status"] == "done"
    assert completed_task.status_code == 200
    assert completed_task.json()["status"] == "done"
    requirement_history = client.get(f"/api/v1/requirements/{requirement['id']}/status-operations").json()
    task_history = client.get(f"/api/v1/tasks/{task['id']}/status-operations").json()
    assert requirement_history[-1]["action"] == "complete"
    assert task_history[-1]["action"] == "complete"


def test_requirement_complete_requires_linked_tasks_done(client: TestClient):
    project_id = _create_project(client, "Requirement Guard Project")
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": "Requirement with open task"},
    ).json()
    client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "requirement_id": requirement["id"], "title": "Open linked task"},
    )

    completed = client.post(f"/api/v1/requirements/{requirement['id']}/complete")

    assert completed.status_code == 400
    assert "关联任务" in completed.json()["detail"]
