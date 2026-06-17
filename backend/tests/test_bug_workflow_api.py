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
        f"/api/v1/bugs/{bug_id}/activate",
        json={"verify_result": "failed", "remark": "still reproduces"},
    )
    assert failed.status_code == 200
    assert failed.json()["status"] == "fixing"
    assert failed.json()["verify_result"] == "failed"
    assert failed.json()["reopen_count"] == 1

    closed = client.post(
        f"/api/v1/bugs/{bug_id}/resolve",
        json={"resolution": "已解决", "remark": "patched again"},
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "verifying"

    closed = client.post(
        f"/api/v1/bugs/{bug_id}/close",
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
        "activate",
        "resolve",
        "close",
    ]


def test_bug_resolve_requires_resolution(client: TestClient):
    bug_id = _create_bug(client)
    client.post(f"/api/v1/bugs/{bug_id}/start-fixing", json={})

    response = client.post(f"/api/v1/bugs/{bug_id}/resolve", json={})

    assert response.status_code == 422


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
    assert activated.json()["status"] == "fixing"
    assert activated.json()["reopen_count"] == 1
