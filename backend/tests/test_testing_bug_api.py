from uuid import uuid4

from fastapi.testclient import TestClient


def _create_project(client: TestClient) -> int:
    response = client.post("/api/v1/projects", json={"name": f"测试项目-{uuid4().hex[:8]}"})
    assert response.status_code == 200
    return response.json()["id"]


def _create_requirement(client: TestClient, project_id: int, owner_id: int = 1) -> int:
    response = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"测试需求-{uuid4().hex[:8]}", "owner_id": owner_id},
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
            "title": "登录失败提示",
            "case_type": "functional",
            "priority": "high",
            "steps_json": [{"step": "输入错误密码", "expected": "提示登录失败"}],
            "expected_result": "提示登录失败",
        },
    )
    assert created.status_code == 200
    case_id = created.json()["id"]
    assert created.json()["requirement_id"] == requirement_id

    updated = client.patch(f"/api/v1/test-cases/{case_id}", json={"status": "inactive"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "inactive"

    deleted = client.delete(f"/api/v1/test-cases/{case_id}")
    assert deleted.status_code == 204


def test_test_run_selects_cases_and_records_execution_result(client: TestClient):
    project_id = _create_project(client)
    case = client.post("/api/v1/test-cases", json={"project_id": project_id, "title": "创建项目成功"})
    assert case.status_code == 200
    case_id = case.json()["id"]

    run = client.post("/api/v1/test-runs", json={"project_id": project_id, "name": "MVP 回归测试"})
    assert run.status_code == 200
    run_id = run.json()["id"]

    selected = client.post(f"/api/v1/test-runs/{run_id}/cases", json={"test_case_ids": [case_id], "tester_id": 1})
    assert selected.status_code == 200
    run_case = selected.json()[0]
    assert run_case["test_run_id"] == run_id
    assert run_case["test_case_id"] == case_id

    executed = client.patch(f"/api/v1/test-run-cases/{run_case['id']}", json={"result": "failed", "remark": "按钮无响应"})
    assert executed.status_code == 200
    assert executed.json()["result"] == "failed"

    listed = client.get("/api/v1/test-run-cases")
    assert listed.status_code == 200
    assert any(item["id"] == run_case["id"] for item in listed.json())


def test_failed_test_result_can_create_bug_with_requirement_owner(client: TestClient):
    project_id = _create_project(client)
    requirement_id = _create_requirement(client, project_id, owner_id=1)
    case = client.post(
        "/api/v1/test-cases",
        json={"project_id": project_id, "requirement_id": requirement_id, "title": "提交表单失败"},
    )
    run = client.post("/api/v1/test-runs", json={"project_id": project_id, "name": "表单回归"})
    selected = client.post(
        f"/api/v1/test-runs/{run.json()['id']}/cases",
        json={"test_case_ids": [case.json()["id"]], "tester_id": 1},
    ).json()[0]
    client.patch(f"/api/v1/test-run-cases/{selected['id']}", json={"result": "failed"})

    bug = client.post(
        f"/api/v1/test-run-cases/{selected['id']}/bugs",
        json={"title": "提交表单失败", "actual_result": "接口返回 500"},
    )
    assert bug.status_code == 200
    data = bug.json()
    assert data["project_id"] == project_id
    assert data["requirement_id"] == requirement_id
    assert data["test_case_id"] == case.json()["id"]
    assert data["test_run_id"] == run.json()["id"]
    assert data["owner_id"] == 1
    assert data["status"] == "open"

    transitioned = client.patch(f"/api/v1/bugs/{data['id']}", json={"status": "verifying"})
    assert transitioned.status_code == 200
    assert transitioned.json()["status"] == "verifying"
