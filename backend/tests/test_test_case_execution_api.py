from uuid import uuid4

from fastapi.testclient import TestClient

from app.services.bug_service import BUG_RESOLUTIONS


def _valid_resolution() -> str:
    return sorted(BUG_RESOLUTIONS)[0]


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


def _create_test_case_for_requirement(client: TestClient, project_id: int, requirement_id: int, title: str | None = None) -> int:
    response = client.post(
        "/api/v1/test-cases",
        json={
            "project_id": project_id,
            "requirement_id": requirement_id,
            "title": title or f"Requirement case-{uuid4().hex[:8]}",
            "steps_json": [{"step": "verify requirement", "expected": "works"}],
        },
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


def test_failed_test_case_execution_creates_bug_with_case_iteration_and_can_edit_iteration(client: TestClient):
    project_id = _create_project(client)
    requirement_id = _create_requirement(client, project_id, owner_id=1)
    iteration = client.post(
        "/api/v1/iterations",
        json={"project_ids": [project_id], "name": f"Iteration-{uuid4().hex[:8]}"},
    )
    assert iteration.status_code == 200
    iteration_id = iteration.json()["id"]
    next_iteration = client.post(
        "/api/v1/iterations",
        json={"project_ids": [project_id], "name": f"Next Iteration-{uuid4().hex[:8]}"},
    )
    assert next_iteration.status_code == 200
    next_iteration_id = next_iteration.json()["id"]
    linked = client.post(f"/api/v1/iterations/{iteration_id}/requirements", json={"requirement_ids": [requirement_id]})
    assert linked.status_code == 200

    case = client.post(
        "/api/v1/test-cases",
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
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
        json={"title": "Submit order fails", "bug_type": "浠ｇ爜閿欒", "severity": "1", "priority": "2"},
    )
    assert bug.status_code == 200
    data = bug.json()
    assert data["project_id"] == project_id
    assert data["requirement_id"] == requirement_id
    assert data["iteration_id"] == iteration_id
    assert data["test_case_id"] == case_id
    assert data["owner_id"] is None
    assert data["bug_type"] == "浠ｇ爜閿欒"
    assert "submit order" in data["reproduce_steps"]
    assert "HTTP 500" in data["reproduce_steps"]

    detail = client.get(f"/api/v1/iterations/{iteration_id}/detail")
    assert detail.status_code == 200
    assert any(item["id"] == data["id"] for item in detail.json()["bugs"])

    updated = client.patch(
        f"/api/v1/bugs/{data['id']}",
        json={"iteration_id": next_iteration_id},
    )
    assert updated.status_code == 200
    assert updated.json()["iteration_id"] == next_iteration_id

    detail_after_update = client.get(f"/api/v1/iterations/{next_iteration_id}/detail")
    assert detail_after_update.status_code == 200
    assert any(item["id"] == data["id"] for item in detail_after_update.json()["bugs"])


def test_failed_test_case_bug_uses_requirement_iteration_when_case_has_no_direct_iteration(client: TestClient):
    project_id = _create_project(client)
    requirement_id = _create_requirement(client, project_id, owner_id=1)
    iteration = client.post(
        "/api/v1/iterations",
        json={"project_ids": [project_id], "name": f"Requirement Iteration-{uuid4().hex[:8]}"},
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
            "title": "Case inherits requirement iteration",
            "steps_json": [{"step": "submit form", "expected": "success"}],
        },
    )
    assert case.status_code == 200
    assert case.json()["iteration_id"] is None
    case_id = case.json()["id"]
    executed = client.post(
        f"/api/v1/test-cases/{case_id}/executions",
        json={"steps_result_json": [{"step": "submit form", "expected": "success", "result": "failed", "actual": "500"}]},
    )
    assert executed.status_code == 200

    bug = client.post(f"/api/v1/test-cases/{case_id}/bugs", json={"title": "Inherited iteration bug"})

    assert bug.status_code == 200
    assert bug.json()["iteration_id"] == iteration_id


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


def test_failed_test_case_execution_marks_pending_requirement_validation_failed(client: TestClient):
    project_id = _create_project(client)
    requirement_id = _create_requirement(client, project_id)
    case_id = _create_test_case_for_requirement(client, project_id, requirement_id)
    client.post(f"/api/v1/requirements/{requirement_id}/activate")
    submitted = client.post(f"/api/v1/requirements/{requirement_id}/complete")
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "pending_validation"

    executed = client.post(
        f"/api/v1/test-cases/{case_id}/executions",
        json={"steps_result_json": [{"step": "verify requirement", "expected": "works", "result": "failed", "actual": "error"}]},
    )

    assert executed.status_code == 200
    assert client.get(f"/api/v1/requirements/{requirement_id}").json()["status"] == "validation_failed"


def test_passed_related_cases_complete_pending_requirement_when_no_open_bugs(client: TestClient):
    project_id = _create_project(client)
    requirement_id = _create_requirement(client, project_id)
    first_case_id = _create_test_case_for_requirement(client, project_id, requirement_id, "Pass case")
    second_case_id = _create_test_case_for_requirement(client, project_id, requirement_id, "Ignore case")
    client.post(f"/api/v1/requirements/{requirement_id}/activate")
    client.post(f"/api/v1/requirements/{requirement_id}/complete")

    first = client.post(
        f"/api/v1/test-cases/{first_case_id}/executions",
        json={"steps_result_json": [{"step": "verify requirement", "expected": "works", "result": "passed", "actual": "works"}]},
    )
    assert first.status_code == 200
    assert client.get(f"/api/v1/requirements/{requirement_id}").json()["status"] == "pending_validation"

    second = client.post(
        f"/api/v1/test-cases/{second_case_id}/executions",
        json={"steps_result_json": [{"step": "verify requirement", "expected": "works", "result": "ignored", "actual": ""}]},
    )

    assert second.status_code == 200
    assert client.get(f"/api/v1/requirements/{requirement_id}").json()["status"] == "done"


def test_requirement_validation_cases_returns_cases_and_summary(client: TestClient):
    project_id = _create_project(client)
    requirement_id = _create_requirement(client, project_id)
    passed_case = _create_test_case_for_requirement(client, project_id, requirement_id, "Passed case")
    failed_case = _create_test_case_for_requirement(client, project_id, requirement_id, "Failed case")
    pending_case = _create_test_case_for_requirement(client, project_id, requirement_id, "Pending case")
    client.post(
        f"/api/v1/test-cases/{passed_case}/executions",
        json={"steps_result_json": [{"step": "verify", "expected": "ok", "result": "passed", "actual": "ok"}]},
    )
    client.post(
        f"/api/v1/test-cases/{failed_case}/executions",
        json={"steps_result_json": [{"step": "verify", "expected": "ok", "result": "failed", "actual": "bad"}]},
    )
    bug = client.post(f"/api/v1/test-cases/{failed_case}/bugs", json={"title": "Failed case bug"})
    assert bug.status_code == 200

    response = client.get(f"/api/v1/requirements/{requirement_id}/validation-cases")

    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == {"total": 3, "passed": 1, "failed": 1, "blocked": 0, "ignored": 0, "pending": 1}
    rows = {item["id"]: item for item in data["items"]}
    assert rows[passed_case]["latest_result"] == "passed"
    assert rows[failed_case]["latest_result"] == "failed"
    assert rows[failed_case]["open_bug_count"] == 1
    assert rows[pending_case]["latest_result"] is None


def test_bug_validation_context_prefers_source_case_or_requirement_cases(client: TestClient):
    project_id = _create_project(client)
    requirement_id = _create_requirement(client, project_id)
    case_a = _create_test_case_for_requirement(client, project_id, requirement_id, "Case A")
    case_b = _create_test_case_for_requirement(client, project_id, requirement_id, "Case B")

    direct_bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "requirement_id": requirement_id, "test_case_id": case_b, "title": "Direct case bug"},
    )
    assert direct_bug.status_code == 200
    direct_context = client.get(f"/api/v1/bugs/{direct_bug.json()['id']}/validation-context")
    assert direct_context.status_code == 200
    assert direct_context.json()["source"] == "test_case"
    assert [item["id"] for item in direct_context.json()["items"]] == [case_b]

    requirement_bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "requirement_id": requirement_id, "title": "Requirement bug"},
    )
    assert requirement_bug.status_code == 200
    requirement_context = client.get(f"/api/v1/bugs/{requirement_bug.json()['id']}/validation-context")
    assert requirement_context.status_code == 200
    assert requirement_context.json()["source"] == "requirement"
    assert {item["id"] for item in requirement_context.json()["items"]} == {case_a, case_b}


def test_validation_failed_requirement_is_completed_when_all_latest_case_results_pass(client: TestClient):
    project_id = _create_project(client)
    requirement_id = _create_requirement(client, project_id)
    case_id = _create_test_case_for_requirement(client, project_id, requirement_id)
    client.post(f"/api/v1/requirements/{requirement_id}/activate")
    client.post(f"/api/v1/requirements/{requirement_id}/complete")
    client.post(
        f"/api/v1/test-cases/{case_id}/executions",
        json={"steps_result_json": [{"step": "verify requirement", "expected": "works", "result": "failed", "actual": "error"}]},
    )
    bug = client.post(f"/api/v1/test-cases/{case_id}/bugs", json={"title": "Validation bug"})
    assert bug.status_code == 200

    blocked = client.post(f"/api/v1/requirements/{requirement_id}/complete")
    assert blocked.status_code == 400

    assert client.post(f"/api/v1/bugs/{bug.json()['id']}/start-fixing", json={}).status_code == 200
    assert client.post(f"/api/v1/bugs/{bug.json()['id']}/resolve", json={"resolution": _valid_resolution()}).status_code == 200
    passed = client.post(
        f"/api/v1/test-cases/{case_id}/executions",
        json={"steps_result_json": [{"step": "verify requirement", "expected": "works", "result": "passed", "actual": "works"}]},
    )
    assert passed.status_code == 200
    assert client.get(f"/api/v1/requirements/{requirement_id}").json()["status"] == "done"


def test_validation_failed_requirement_waits_until_every_case_latest_result_passes(client: TestClient):
    project_id = _create_project(client)
    requirement_id = _create_requirement(client, project_id)
    case_a = _create_test_case_for_requirement(client, project_id, requirement_id, "Case A")
    case_b = _create_test_case_for_requirement(client, project_id, requirement_id, "Case B")
    case_c = _create_test_case_for_requirement(client, project_id, requirement_id, "Case C")
    client.post(f"/api/v1/requirements/{requirement_id}/activate")
    client.post(f"/api/v1/requirements/{requirement_id}/complete")
    client.post(
        f"/api/v1/test-cases/{case_a}/executions",
        json={"steps_result_json": [{"step": "verify A", "expected": "works", "result": "passed", "actual": "works"}]},
    )
    client.post(
        f"/api/v1/test-cases/{case_b}/executions",
        json={"steps_result_json": [{"step": "verify B", "expected": "works", "result": "failed", "actual": "error"}]},
    )
    assert client.get(f"/api/v1/requirements/{requirement_id}").json()["status"] == "validation_failed"
    assert client.post(f"/api/v1/test-cases/{case_b}/bugs", json={"title": "Case B bug"}).status_code == 200

    client.post(
        f"/api/v1/test-cases/{case_b}/executions",
        json={"steps_result_json": [{"step": "verify B", "expected": "works", "result": "passed", "actual": "works"}]},
    )
    assert client.get(f"/api/v1/requirements/{requirement_id}").json()["status"] == "validation_failed"

    client.post(
        f"/api/v1/test-cases/{case_c}/executions",
        json={"steps_result_json": [{"step": "verify C", "expected": "works", "result": "ignored", "actual": ""}]},
    )
    assert client.get(f"/api/v1/requirements/{requirement_id}").json()["status"] == "done"


def test_linked_bug_verify_passed_requires_latest_case_result_passed(client: TestClient):
    project_id = _create_project(client)
    requirement_id = _create_requirement(client, project_id)
    case_id = _create_test_case_for_requirement(client, project_id, requirement_id)
    client.post(f"/api/v1/requirements/{requirement_id}/activate")
    client.post(f"/api/v1/requirements/{requirement_id}/complete")
    client.post(
        f"/api/v1/test-cases/{case_id}/executions",
        json={"steps_result_json": [{"step": "verify requirement", "expected": "works", "result": "failed", "actual": "error"}]},
    )
    bug = client.post(f"/api/v1/test-cases/{case_id}/bugs", json={"title": "Validation bug"})
    assert bug.status_code == 200
    assert client.post(f"/api/v1/bugs/{bug.json()['id']}/start-fixing", json={}).status_code == 200
    assert client.post(f"/api/v1/bugs/{bug.json()['id']}/resolve", json={"resolution": _valid_resolution()}).status_code == 200

    verify_passed = client.post(f"/api/v1/bugs/{bug.json()['id']}/verify-passed", json={"remark": "verified"})

    assert verify_passed.status_code == 400
    assert client.get(f"/api/v1/bugs/{bug.json()['id']}").json()["status"] == "verifying"
    assert client.get(f"/api/v1/requirements/{requirement_id}").json()["status"] == "validation_failed"


def test_bug_verification_failure_keeps_requirement_validation_failed(client: TestClient):
    project_id = _create_project(client)
    requirement_id = _create_requirement(client, project_id)
    case_id = _create_test_case_for_requirement(client, project_id, requirement_id)
    client.post(f"/api/v1/requirements/{requirement_id}/activate")
    client.post(f"/api/v1/requirements/{requirement_id}/complete")
    client.post(
        f"/api/v1/test-cases/{case_id}/executions",
        json={"steps_result_json": [{"step": "verify requirement", "expected": "works", "result": "failed", "actual": "error"}]},
    )
    bug = client.post(f"/api/v1/test-cases/{case_id}/bugs", json={"title": "Validation bug"})
    assert bug.status_code == 200
    assert client.post(f"/api/v1/bugs/{bug.json()['id']}/start-fixing", json={}).status_code == 200
    assert client.post(f"/api/v1/bugs/{bug.json()['id']}/resolve", json={"resolution": _valid_resolution()}).status_code == 200

    failed = client.post(
        f"/api/v1/test-cases/{case_id}/executions",
        json={"steps_result_json": [{"step": "verify requirement", "expected": "works", "result": "failed", "actual": "still wrong"}]},
    )
    assert failed.status_code == 200
    verify_failed = client.post(f"/api/v1/bugs/{bug.json()['id']}/verify-failed", json={"remark": "still failed"})

    assert verify_failed.status_code == 200
    assert verify_failed.json()["status"] == "reopened"
    assert client.get(f"/api/v1/requirements/{requirement_id}").json()["status"] == "validation_failed"
