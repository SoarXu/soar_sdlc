from uuid import uuid4

from fastapi.testclient import TestClient


def _create_project(client: TestClient) -> int:
    response = client.post("/api/v1/projects", json={"name": f"Project-{uuid4().hex[:8]}"})
    assert response.status_code == 200
    return response.json()["id"]


def _create_test_case(client: TestClient, project_id: int) -> int:
    response = client.post(
        "/api/v1/test-cases",
        json={
            "project_id": project_id,
            "title": "Execute login case",
            "case_type": "functional",
            "test_scope": "functional_test",
            "priority": "high",
            "steps_json": [
                {"step": "open login page", "expected": "login page visible"},
                {"step": "submit wrong password", "expected": "error message visible"},
            ],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "priority" not in data
    return data["id"]


def test_test_case_execution_records_history_and_latest_result(client: TestClient):
    project_id = _create_project(client)
    case_id = _create_test_case(client, project_id)

    executed = client.post(
        f"/api/v1/test-cases/{case_id}/executions",
        json={
            "executor_id": 1,
            "execute_time": "2026-06-11T22:30:00",
            "steps_result_json": [
                {
                    "step": "open login page",
                    "expected": "login page visible",
                    "result": "passed",
                    "actual": "page loaded",
                },
                {
                    "step": "submit wrong password",
                    "expected": "error message visible",
                    "result": "blocked",
                    "actual": "test account locked",
                },
            ],
        },
    )
    assert executed.status_code == 200
    assert executed.json()["result"] == "blocked"

    cases = client.get("/api/v1/test-cases")
    assert cases.status_code == 200
    case = next(item for item in cases.json() if item["id"] == case_id)
    assert case["last_execute_time"] == "2026-06-11T22:30:00"
    assert case["last_execute_result"] == "blocked"
    assert "priority" not in case

    history = client.get(f"/api/v1/test-cases/{case_id}/executions")
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["steps_result_json"][1]["actual"] == "test account locked"


def test_test_case_execution_result_failed_takes_precedence(client: TestClient):
    project_id = _create_project(client)
    case_id = _create_test_case(client, project_id)

    executed = client.post(
        f"/api/v1/test-cases/{case_id}/executions",
        json={
            "steps_result_json": [
                {"step": "step 1", "expected": "ok", "result": "blocked", "actual": "blocked"},
                {"step": "step 2", "expected": "ok", "result": "failed", "actual": "wrong result"},
            ],
        },
    )
    assert executed.status_code == 200
    assert executed.json()["result"] == "failed"


def test_test_case_execution_result_all_ignored(client: TestClient):
    project_id = _create_project(client)
    case_id = _create_test_case(client, project_id)

    executed = client.post(
        f"/api/v1/test-cases/{case_id}/executions",
        json={"steps_result_json": [{"step": "step 1", "expected": "ok", "result": "ignored", "actual": ""}]},
    )
    assert executed.status_code == 200
    assert executed.json()["result"] == "ignored"
