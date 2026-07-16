from uuid import uuid4

from fastapi.testclient import TestClient


def _create_project(client: TestClient) -> int:
    response = client.post("/api/v1/projects", json={"name": f"Bug API Project {uuid4().hex[:8]}"})
    assert response.status_code == 200
    return response.json()["id"]


def _create_bug(client: TestClient, **overrides) -> dict:
    payload = {
        "project_id": _create_project(client),
        "title": f"Bug API {uuid4().hex[:8]}",
    }
    payload.update(overrides)
    response = client.post("/api/v1/bugs", json=payload)
    assert response.status_code == 200
    assert response.json()["status_name"] == "待处理"
    return response.json()


def test_bug_crud_keeps_status_changes_on_workflow_runtime(client: TestClient):
    bug = _create_bug(client)

    detail = client.get(f"/api/v1/bugs/{bug['id']}")
    updated = client.patch(f"/api/v1/bugs/{bug['id']}", json={"title": "Updated bug title", "status": "closed"})
    history = client.get(f"/api/v1/bugs/{bug['id']}/status-operations")

    assert detail.status_code == 200
    assert updated.status_code == 422
    unchanged = client.get(f"/api/v1/bugs/{bug['id']}").json()
    assert unchanged["title"] == bug["title"]
    assert unchanged["status_name"] == "待处理"
    assert history.status_code == 200


def test_legacy_bug_status_endpoints_are_removed(client: TestClient):
    bug = _create_bug(client)

    for path in [
        "start-fixing",
        "resolve",
        "verify-passed",
        "verify-failed",
        "suspend",
        "close",
        "activate",
    ]:
        response = client.post(f"/api/v1/bugs/{bug['id']}/{path}", json={})
        assert response.status_code == 404


def test_bug_create_and_update_reject_closed_iteration(client: TestClient):
    project_id = _create_project(client)
    iteration = client.post(
        "/api/v1/iterations",
        json={"project_ids": [project_id], "name": f"Completed Iteration {uuid4().hex[:8]}", "status": "completed"},
    )
    assert iteration.status_code == 200
    iteration_id = iteration.json()["id"]

    created_with_finished_iteration = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": f"Bug {uuid4().hex[:8]}"},
    )
    bug = client.post("/api/v1/bugs", json={"project_id": project_id, "title": f"Bug {uuid4().hex[:8]}"})
    updated_with_finished_iteration = client.patch(
        f"/api/v1/bugs/{bug.json()['id']}",
        json={"iteration_id": iteration_id},
    )

    assert created_with_finished_iteration.status_code == 400
    assert bug.status_code == 200
    assert updated_with_finished_iteration.status_code == 400
