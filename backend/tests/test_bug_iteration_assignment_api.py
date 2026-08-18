from uuid import uuid4

from fastapi.testclient import TestClient


def _create_project(client: TestClient) -> int:
    response = client.post("/api/v1/projects", json={"name": f"Bug iteration {uuid4().hex[:8]}"})
    assert response.status_code == 200
    return response.json()["id"]


def _create_iteration(client: TestClient, project_id: int, name: str, *, active: bool = False) -> int:
    response = client.post(
        "/api/v1/iterations",
        json={"project_ids": [project_id], "name": name},
    )
    assert response.status_code == 200
    iteration_id = response.json()["id"]
    if active:
        started = client.post(
            f"/api/v1/workflow-runtime/iteration/{iteration_id}/transition",
            json={"action_key": "start"},
        )
        assert started.status_code == 200
    return iteration_id


def test_manual_bug_creation_requires_explicit_eligible_iteration(client: TestClient):
    project_id = _create_project(client)

    missing_iteration = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "title": "Missing iteration"},
        headers={"X-Test-Require-Explicit-Iteration": "1"},
    )
    planning_iteration_id = _create_iteration(client, project_id, "Planning")
    planning = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "iteration_id": planning_iteration_id, "title": "Planning bug"},
    )
    active_iteration_id = _create_iteration(client, project_id, "Active", active=True)
    active = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "iteration_id": active_iteration_id, "title": "Active bug"},
    )

    assert missing_iteration.status_code == 422
    assert missing_iteration.json()["detail"] == {
        "code": "ITERATION_REQUIRED",
        "message": "请选择规划中或进行中的迭代",
    }
    assert planning.status_code == 200
    assert planning.json()["iteration_id"] == planning_iteration_id
    assert active.status_code == 200
    assert active.json()["iteration_id"] == active_iteration_id


def test_bug_in_non_active_iteration_has_no_available_workflow_transitions(client: TestClient):
    project_id = _create_project(client)
    planning_iteration_id = _create_iteration(client, project_id, "Planning")
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "iteration_id": planning_iteration_id, "title": "Planning bug"},
    )
    assert bug.status_code == 200

    listed = client.get(f"/api/v1/workflow-runtime/bug/{bug.json()['id']}/transitions")
    batch = client.post(
        "/api/v1/workflow-runtime/transitions/batch",
        json={"items": [{"object_type": "bug", "id": bug.json()["id"]}]},
    )

    assert listed.status_code == 200
    assert listed.json() == []
    assert batch.status_code == 200
    assert batch.json()["items"][0]["transitions"] == []
