from uuid import uuid4

from fastapi.testclient import TestClient


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
