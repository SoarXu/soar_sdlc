from uuid import uuid4

from fastapi.testclient import TestClient

from app.services.bug_service import BUG_RESOLUTIONS


def _valid_resolution() -> str:
    return sorted(BUG_RESOLUTIONS)[0]


def _create_bug(client: TestClient, **overrides) -> dict:
    project = client.post("/api/v1/projects", json={"name": f"Bug Flow Project {uuid4().hex[:8]}"})
    assert project.status_code == 200
    payload = {
        "project_id": project.json()["id"],
        "title": f"Bug Flow {uuid4().hex[:8]}",
    }
    payload.update(overrides)
    bug = client.post("/api/v1/bugs", json=payload)
    assert bug.status_code == 200
    assert bug.json()["status"] == "pending_handling"
    return bug.json()


def test_bug_legacy_endpoints_follow_default_template_flow(client: TestClient):
    bug = _create_bug(client)

    fixing = client.post(f"/api/v1/bugs/{bug['id']}/start-fixing", json={"remark": "start fixing"})
    assert fixing.status_code == 200
    assert fixing.json()["status"] == "fixing"

    submitted = client.post(
        f"/api/v1/bugs/{bug['id']}/resolve",
        json={"resolution": _valid_resolution(), "remark": "patched validation"},
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "pending_verification"
    assert submitted.json()["resolution"] == _valid_resolution()
    assert submitted.json()["resolve_time"] is not None

    failed = client.post(
        f"/api/v1/bugs/{bug['id']}/verify-failed",
        json={"verify_result": "failed", "remark": "still reproduces"},
    )
    assert failed.status_code == 200
    assert failed.json()["status"] == "pending_handling"
    assert failed.json()["verify_result"] == "failed"
    assert failed.json()["reopen_count"] == 1

    fixing_again = client.post(f"/api/v1/bugs/{bug['id']}/start-fixing", json={"remark": "retry"})
    assert fixing_again.status_code == 200
    assert fixing_again.json()["status"] == "fixing"

    submitted_again = client.post(
        f"/api/v1/bugs/{bug['id']}/resolve",
        json={"resolution": _valid_resolution(), "remark": "patched again"},
    )
    assert submitted_again.status_code == 200
    assert submitted_again.json()["status"] == "pending_verification"

    verified = client.post(
        f"/api/v1/bugs/{bug['id']}/verify-passed",
        json={"verify_result": "passed", "remark": "verified"},
    )
    assert verified.status_code == 200
    assert verified.json()["status"] == "verified"
    assert verified.json()["verify_result"] == "passed"
    assert verified.json()["verify_time"] is not None

    closed = client.post(f"/api/v1/bugs/{bug['id']}/close", json={"reason": "verified done"})
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"

    reactivated = client.post(f"/api/v1/bugs/{bug['id']}/activate", json={"remark": "reopen closed bug"})
    assert reactivated.status_code == 200
    assert reactivated.json()["status"] == "pending_handling"
    assert reactivated.json()["reopen_count"] == 2

    history = client.get(f"/api/v1/bugs/{bug['id']}/status-operations")
    assert history.status_code == 200
    assert [item["action"] for item in history.json()] == [
        "confirm_bug_type",
        "submit_verification",
        "verification_failed",
        "confirm_bug_type",
        "submit_verification",
        "verification_passed",
        "close",
        "activate",
    ]


def test_bug_resolve_requires_resolution(client: TestClient):
    bug = _create_bug(client)
    client.post(f"/api/v1/bugs/{bug['id']}/start-fixing", json={})

    response = client.post(f"/api/v1/bugs/{bug['id']}/resolve", json={})

    assert response.status_code == 422


def test_start_fixing_bug_rejects_closed_iteration(client: TestClient):
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
    assert "iteration" in response.json()["detail"].lower()


def test_bug_create_and_update_reject_closed_iteration(client: TestClient):
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


def test_bug_detail_and_resolution_options(client: TestClient):
    bug = _create_bug(client)

    detail = client.get(f"/api/v1/bugs/{bug['id']}")
    assert detail.status_code == 200
    assert detail.json()["id"] == bug["id"]

    client.post(f"/api/v1/bugs/{bug['id']}/start-fixing", json={})
    invalid = client.post(f"/api/v1/bugs/{bug['id']}/resolve", json={"resolution": "fixed"})
    assert invalid.status_code == 422

    valid = client.post(f"/api/v1/bugs/{bug['id']}/resolve", json={"resolution": _valid_resolution()})
    assert valid.status_code == 200
    assert valid.json()["resolution"] == _valid_resolution()
    assert valid.json()["status"] == "pending_verification"


def test_bug_direct_close_is_blocked_before_verified(client: TestClient):
    bug = _create_bug(client)

    blocked = client.post(f"/api/v1/bugs/{bug['id']}/close", json={"reason": "not required"})

    assert blocked.status_code == 400
