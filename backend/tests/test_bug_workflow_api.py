from uuid import uuid4

from fastapi.testclient import TestClient


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
        json={"resolution": "fixed", "remark": "patched validation"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["resolution"] == "fixed"
    assert resolved.json()["resolve_time"] is not None

    verifying = client.post(f"/api/v1/bugs/{bug_id}/start-verifying", json={"remark": "qa verifying"})
    assert verifying.status_code == 200
    assert verifying.json()["status"] == "verifying"

    failed = client.post(
        f"/api/v1/bugs/{bug_id}/verify-failed",
        json={"verify_result": "failed", "remark": "still reproduces"},
    )
    assert failed.status_code == 200
    assert failed.json()["status"] == "reopened"
    assert failed.json()["verify_result"] == "failed"
    assert failed.json()["reopen_count"] == 1

    refixing = client.post(f"/api/v1/bugs/{bug_id}/start-fixing", json={"remark": "fix again"})
    assert refixing.status_code == 200
    assert refixing.json()["status"] == "fixing"

    client.post(f"/api/v1/bugs/{bug_id}/resolve", json={"resolution": "fixed", "remark": "patched again"})
    client.post(f"/api/v1/bugs/{bug_id}/start-verifying", json={"remark": "verify again"})
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
        "start_verifying",
        "verify_failed",
        "start_fixing",
        "resolve",
        "start_verifying",
        "verify_passed",
    ]


def test_bug_resolve_requires_resolution(client: TestClient):
    bug_id = _create_bug(client)
    client.post(f"/api/v1/bugs/{bug_id}/start-fixing", json={})

    response = client.post(f"/api/v1/bugs/{bug_id}/resolve", json={})

    assert response.status_code == 422
