from uuid import uuid4

from fastapi.testclient import TestClient

from app.services.bug_service import BUG_RESOLUTIONS


def _valid_resolution() -> str:
    return sorted(BUG_RESOLUTIONS)[0]


def _create_bug(client: TestClient) -> int:
    project = client.post("/api/v1/projects", json={"name": f"Bug Flow Project {uuid4().hex[:8]}"})
    assert project.status_code == 200
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project.json()["id"], "title": f"Bug Flow {uuid4().hex[:8]}"},
    )
    assert bug.status_code == 200
    assert bug.json()["status"] == "open"
    return bug.json()["id"]


def test_bug_status_flow_records_resolution_verification_and_reopen(client: TestClient):
    bug_id = _create_bug(client)

    fixing = client.post(f"/api/v1/bugs/{bug_id}/start-fixing", json={"remark": "start fixing"})
    assert fixing.status_code == 200
    assert fixing.json()["status"] == "fixing"

    resolved = client.post(
        f"/api/v1/bugs/{bug_id}/resolve",
        json={"resolution": "已解决", "remark": "patched validation"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "verifying"
    assert resolved.json()["resolution"] == "已解决"
    assert resolved.json()["resolve_time"] is not None

    failed = client.post(
        f"/api/v1/bugs/{bug_id}/verify-failed",
        json={"verify_result": "failed", "remark": "still reproduces"},
    )
    assert failed.status_code == 200
    assert failed.json()["status"] == "reopened"
    assert failed.json()["verify_result"] == "failed"
    assert failed.json()["reopen_count"] == 1

    fixing_again = client.post(f"/api/v1/bugs/{bug_id}/start-fixing", json={"remark": "confirm reopened bug"})
    assert fixing_again.status_code == 200
    assert fixing_again.json()["status"] == "fixing"

    resolved_again = client.post(
        f"/api/v1/bugs/{bug_id}/resolve",
        json={"resolution": "已解决", "remark": "patched again"},
    )
    assert resolved_again.status_code == 200
    assert resolved_again.json()["status"] == "verifying"

    closed = client.post(
        f"/api/v1/bugs/{bug_id}/verify-passed",
        json={"verify_result": "passed", "remark": "verified"},
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
    assert closed.json()["verify_result"] == "passed"
    assert closed.json()["verify_time"] is not None

    history = client.get(f"/api/v1/bugs/{bug_id}/status-operations")
    assert history.status_code == 200
    actions = [item["action"] for item in history.json()]
    assert actions == [
        "start_fixing",
        "resolve",
        "verify_failed",
        "start_fixing",
        "resolve",
        "verify_passed",
    ]


def test_bug_resolve_requires_resolution(client: TestClient):
    bug_id = _create_bug(client)
    client.post(f"/api/v1/bugs/{bug_id}/start-fixing", json={})

    response = client.post(f"/api/v1/bugs/{bug_id}/resolve", json={})

    assert response.status_code == 422


def test_start_fixing_bug_rejects_finished_iteration(client: TestClient):
    project = client.post("/api/v1/projects", json={"name": f"Bug Iteration Project {uuid4().hex[:8]}"})
    assert project.status_code == 200
    project_id = project.json()["id"]
    iteration = client.post(
        "/api/v1/iterations",
        json={"project_ids": [project_id], "name": f"Finished Iteration {uuid4().hex[:8]}", "status": "finished"},
    )
    assert iteration.status_code == 200
    bug = client.post("/api/v1/bugs", json={"project_id": project_id, "title": f"Bug {uuid4().hex[:8]}"})
    assert bug.status_code == 200

    response = client.post(
        f"/api/v1/bugs/{bug.json()['id']}/start-fixing",
        json={"iteration_id": iteration.json()["id"]},
    )

    assert response.status_code == 400
    assert "已结束" in response.json()["detail"]


def test_bug_create_and_update_reject_finished_iteration(client: TestClient):
    project = client.post("/api/v1/projects", json={"name": f"Bug Edit Iteration Project {uuid4().hex[:8]}"})
    assert project.status_code == 200
    project_id = project.json()["id"]
    iteration = client.post(
        "/api/v1/iterations",
        json={"project_ids": [project_id], "name": f"Finished Edit Iteration {uuid4().hex[:8]}", "status": "finished"},
    )
    assert iteration.status_code == 200
    iteration_id = iteration.json()["id"]

    created_with_finished_iteration = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": f"Bug {uuid4().hex[:8]}"},
    )
    assert created_with_finished_iteration.status_code == 400

    bug = client.post("/api/v1/bugs", json={"project_id": project_id, "title": f"Bug {uuid4().hex[:8]}"})
    assert bug.status_code == 200
    updated_with_finished_iteration = client.patch(
        f"/api/v1/bugs/{bug.json()['id']}",
        json={"iteration_id": iteration_id},
    )
    assert updated_with_finished_iteration.status_code == 400


def test_bug_update_accepts_parent_project_unfinished_iteration(client: TestClient):
    parent = client.post("/api/v1/projects", json={"name": f"Parent Bug Project {uuid4().hex[:8]}"})
    assert parent.status_code == 200
    parent_id = parent.json()["id"]
    child = client.post(
        "/api/v1/projects",
        json={"name": f"Child Bug Project {uuid4().hex[:8]}", "parent_id": parent_id},
    )
    assert child.status_code == 200
    child_id = child.json()["id"]
    parent_iteration = client.post(
        "/api/v1/iterations",
        json={"project_ids": [parent_id], "name": f"Parent Iteration {uuid4().hex[:8]}", "status": "active"},
    )
    assert parent_iteration.status_code == 200
    bug = client.post("/api/v1/bugs", json={"project_id": child_id, "title": f"Child Bug {uuid4().hex[:8]}"})
    assert bug.status_code == 200

    response = client.patch(
        f"/api/v1/bugs/{bug.json()['id']}",
        json={"iteration_id": parent_iteration.json()["id"]},
    )

    assert response.status_code == 200
    assert response.json()["project_id"] == child_id
    assert response.json()["iteration_id"] == parent_iteration.json()["id"]


def test_verify_passed_endpoint_closes_verifying_bug(client: TestClient):
    bug_id = _create_bug(client)
    client.post(f"/api/v1/bugs/{bug_id}/start-fixing", json={})
    client.post(f"/api/v1/bugs/{bug_id}/resolve", json={"resolution": _valid_resolution()})

    response = client.post(f"/api/v1/bugs/{bug_id}/verify-passed", json={"remark": "verified"})

    assert response.status_code == 200
    assert response.json()["status"] == "closed"
    assert response.json()["verify_result"] == "passed"
    assert response.json()["verify_time"] is not None
    history = client.get(f"/api/v1/bugs/{bug_id}/status-operations")
    assert [item["action"] for item in history.json()] == ["start_fixing", "resolve", "verify_passed"]


def test_verify_failed_endpoint_reopens_verifying_bug(client: TestClient):
    bug_id = _create_bug(client)
    client.post(f"/api/v1/bugs/{bug_id}/start-fixing", json={})
    client.post(f"/api/v1/bugs/{bug_id}/resolve", json={"resolution": _valid_resolution()})

    response = client.post(f"/api/v1/bugs/{bug_id}/verify-failed", json={"remark": "still failed"})

    assert response.status_code == 200
    assert response.json()["status"] == "reopened"
    assert response.json()["verify_result"] == "failed"
    assert response.json()["verify_time"] is not None
    assert response.json()["reopen_count"] == 1
    history = client.get(f"/api/v1/bugs/{bug_id}/status-operations")
    assert [item["action"] for item in history.json()] == ["start_fixing", "resolve", "verify_failed"]


def test_start_verifying_endpoint_is_not_exposed(client: TestClient):
    bug_id = _create_bug(client)

    response = client.post(f"/api/v1/bugs/{bug_id}/start-verifying", json={})

    assert response.status_code == 404


def test_bug_detail_and_resolution_options(client: TestClient):
    bug_id = _create_bug(client)

    detail = client.get(f"/api/v1/bugs/{bug_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == bug_id

    client.post(f"/api/v1/bugs/{bug_id}/start-fixing", json={})
    invalid = client.post(f"/api/v1/bugs/{bug_id}/resolve", json={"resolution": "fixed"})
    assert invalid.status_code == 422

    valid = client.post(f"/api/v1/bugs/{bug_id}/resolve", json={"resolution": "已解决"})
    assert valid.status_code == 200
    assert valid.json()["resolution"] == "已解决"
    assert valid.json()["status"] == "verifying"


def test_closed_bug_can_be_activated(client: TestClient):
    bug_id = _create_bug(client)
    client.post(f"/api/v1/bugs/{bug_id}/close", json={"reason": "not required"})

    activated = client.post(f"/api/v1/bugs/{bug_id}/activate", json={"remark": "reopen closed bug"})

    assert activated.status_code == 200
    assert activated.json()["status"] == "reopened"
    assert activated.json()["reopen_count"] == 1

    confirmed = client.post(f"/api/v1/bugs/{bug_id}/start-fixing", json={})

    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "fixing"
