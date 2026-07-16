from uuid import uuid4

from fastapi.testclient import TestClient


def _create_project(client: TestClient) -> int:
    response = client.post("/api/v1/projects", json={"name": f"Testing Project {uuid4().hex[:8]}"})
    assert response.status_code == 200
    return response.json()["id"]


def _create_requirement(client: TestClient, project_id: int, owner_id: int = 1) -> int:
    response = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"Testing Requirement {uuid4().hex[:8]}", "owner_id": owner_id},
    )
    assert response.status_code == 200
    return response.json()["id"]


def test_test_case_crud_uses_prd_fields(client: TestClient):
    project_id = _create_project(client)
    requirement_id = _create_requirement(client, project_id)

    created = client.post(
        "/api/v1/test-cases",
        json={
            "project_id": project_id,
            "requirement_id": requirement_id,
            "title": "Login failure prompt",
            "case_type": "functional",
            "test_scope": "functional_test",
            "priority": "high",
            "steps_json": [{"step": "input wrong password", "expected": "show login failure"}],
            "expected_result": "show login failure",
        },
    )
    assert created.status_code == 200
    case_id = created.json()["id"]
    assert created.json()["requirement_id"] == requirement_id
    assert created.json()["test_scope"] == "functional_test"
    assert created.json()["steps_json"] == [{"step": "input wrong password", "expected": "show login failure"}]
    assert "status" not in created.json()

    updated = client.patch(f"/api/v1/test-cases/{case_id}", json={"expected_result": "show login failure and retry"})
    assert updated.status_code == 200
    assert updated.json()["expected_result"] == "show login failure and retry"
    assert "status" not in updated.json()
    assert client.delete(f"/api/v1/test-cases/{case_id}").status_code == 204


def test_test_run_selects_cases_and_records_execution_result(client: TestClient):
    project_id = _create_project(client)
    case = client.post("/api/v1/test-cases", json={"project_id": project_id, "title": "Create project succeeds"})
    assert case.status_code == 200
    run = client.post("/api/v1/test-runs", json={"project_id": project_id, "name": "MVP regression"})
    assert run.status_code == 200
    selected = client.post(f"/api/v1/test-runs/{run.json()['id']}/cases", json={"test_case_ids": [case.json()["id"]], "tester_id": 1})
    assert selected.status_code == 200
    run_case = selected.json()[0]

    executed = client.patch(f"/api/v1/test-run-cases/{run_case['id']}", json={"result": "failed", "remark": "button has no response"})

    assert executed.status_code == 200
    assert executed.json()["result"] == "failed"
    assert any(item["id"] == run_case["id"] for item in client.get("/api/v1/test-run-cases").json())


def test_failed_test_result_can_create_bug_with_requirement_owner(client: TestClient):
    project_id = _create_project(client)
    requirement_id = _create_requirement(client, project_id, owner_id=1)
    case = client.post(
        "/api/v1/test-cases",
        json={"project_id": project_id, "requirement_id": requirement_id, "title": "Submit form fails"},
    )
    run = client.post("/api/v1/test-runs", json={"project_id": project_id, "name": "Form regression"})
    selected = client.post(
        f"/api/v1/test-runs/{run.json()['id']}/cases",
        json={"test_case_ids": [case.json()["id"]], "tester_id": 1},
    ).json()[0]
    client.patch(f"/api/v1/test-run-cases/{selected['id']}", json={"result": "failed"})

    bug = client.post(
        f"/api/v1/test-run-cases/{selected['id']}/bugs",
        json={"title": "Submit form fails", "actual_result": "API returns 500"},
    )

    assert bug.status_code == 200
    data = bug.json()
    assert data["project_id"] == project_id
    assert data["requirement_id"] == requirement_id
    assert data["test_case_id"] == case.json()["id"]
    assert data["test_run_id"] == run.json()["id"]
    assert data["owner_id"] == 1
    assert data["status_name"] == "待处理"
