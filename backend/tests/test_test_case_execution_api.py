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


def _create_requirement(client: TestClient, project_id: int, owner_id: int = 1) -> int:
    response = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"Requirement-{uuid4().hex[:8]}", "owner_id": owner_id},
    )
    assert response.status_code == 200
    return response.json()["id"]


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

    detail = client.get(f"/api/v1/test-cases/{case_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == case_id
    assert detail.json()["last_execute_result"] == "blocked"


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


def test_failed_test_case_execution_creates_bug_without_fix_iteration(client: TestClient):
    project_id = _create_project(client)
    requirement_id = _create_requirement(client, project_id, owner_id=1)
    iteration = client.post(
        "/api/v1/iterations",
        json={"project_ids": [project_id], "name": f"Iteration-{uuid4().hex[:8]}"},
    )
    assert iteration.status_code == 200
    iteration_id = iteration.json()["id"]
    linked = client.post(f"/api/v1/iterations/{iteration_id}/requirements", json={"requirement_ids": [requirement_id]})
    assert linked.status_code == 200

    case = client.post(
        "/api/v1/test-cases",
        json={
            "project_id": project_id,
            "requirement_id": requirement_id,
            "title": "Submit order fails",
            "steps_json": [{"step": "submit order", "expected": "order created"}],
            "expected_result": "order created",
        },
    )
    assert case.status_code == 200
    case_id = case.json()["id"]
    executed = client.post(
        f"/api/v1/test-cases/{case_id}/executions",
        json={
            "executor_id": 1,
            "steps_result_json": [
                {"step": "submit order", "expected": "order created", "result": "failed", "actual": "HTTP 500"},
            ],
        },
    )
    assert executed.status_code == 200

    bug = client.post(
        f"/api/v1/test-cases/{case_id}/bugs",
        json={"title": "Submit order fails", "bug_type": "代码错误", "severity": "1", "priority": "2"},
    )
    assert bug.status_code == 200
    data = bug.json()
    assert data["project_id"] == project_id
    assert data["requirement_id"] == requirement_id
    assert data["iteration_id"] is None
    assert data["test_case_id"] == case_id
    assert data["owner_id"] == 1
    assert data["bug_type"] == "代码错误"
    assert "submit order" in data["reproduce_steps"]
    assert "HTTP 500" in data["reproduce_steps"]

    detail = client.get(f"/api/v1/iterations/{iteration_id}/detail")
    assert detail.status_code == 200
    assert all(item["id"] != data["id"] for item in detail.json()["bugs"])

    confirmed = client.post(
        f"/api/v1/bugs/{data['id']}/start-fixing",
        json={"iteration_id": iteration_id, "remark": "confirm fix iteration"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "fixing"
    assert confirmed.json()["iteration_id"] == iteration_id

    detail_after_confirm = client.get(f"/api/v1/iterations/{iteration_id}/detail")
    assert detail_after_confirm.status_code == 200
    assert any(item["id"] == data["id"] for item in detail_after_confirm.json()["bugs"])


def test_passed_test_case_execution_cannot_create_bug(client: TestClient):
    project_id = _create_project(client)
    case_id = _create_test_case(client, project_id)
    executed = client.post(
        f"/api/v1/test-cases/{case_id}/executions",
        json={"steps_result_json": [{"step": "step 1", "expected": "ok", "result": "passed", "actual": "ok"}]},
    )
    assert executed.status_code == 200

    bug = client.post(f"/api/v1/test-cases/{case_id}/bugs", json={"title": "Should not create"})
    assert bug.status_code == 400
