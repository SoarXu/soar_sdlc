from uuid import uuid4

from fastapi.testclient import TestClient


def test_test_case_scopes_accept_multiple_values_and_preserve_legacy_scope(client: TestClient):
    project = client.post("/api/v1/projects", json={"name": f"Scope list {uuid4().hex[:8]}"})
    assert project.status_code == 200, project.text

    created = client.post(
        "/api/v1/test-cases",
        json={
            "project_id": project.json()["id"],
            "title": "Multiple test scopes",
            "test_scopes": ["functional_test", "system_test"],
        },
    )

    assert created.status_code == 200, created.text
    assert created.json()["test_scopes"] == ["functional_test", "system_test"]
    assert created.json()["test_scope"] == "functional_test"

    legacy = client.post(
        "/api/v1/test-cases",
        json={
            "project_id": project.json()["id"],
            "title": "Legacy scope",
            "test_scope": "smoke_test",
        },
    )

    assert legacy.status_code == 200, legacy.text
    assert legacy.json()["test_scopes"] == ["smoke_test"]
    assert legacy.json()["test_scope"] == "smoke_test"


def test_requirement_validation_cases_returns_multiple_test_scopes(client: TestClient):
    project = client.post("/api/v1/projects", json={"name": f"Scope validation {uuid4().hex[:8]}"})
    assert project.status_code == 200, project.text
    iteration = client.post(
        "/api/v1/iterations",
        json={"name": f"Scope iteration {uuid4().hex[:8]}", "project_ids": [project.json()["id"]]},
    )
    assert iteration.status_code == 200, iteration.text
    requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project.json()["id"],
            "iteration_id": iteration.json()["id"],
            "title": "Scope validation requirement",
        },
    )
    assert requirement.status_code == 200, requirement.text
    test_case = client.post(
        "/api/v1/test-cases",
        json={
            "project_id": project.json()["id"],
            "requirement_id": requirement.json()["id"],
            "title": "Scope validation case",
            "test_scopes": ["functional_test", "system_test"],
        },
    )
    assert test_case.status_code == 200, test_case.text

    response = client.get(f"/api/v1/requirements/{requirement.json()['id']}/validation-cases")

    assert response.status_code == 200, response.text
    assert response.json()["items"] == [
        {
            "id": test_case.json()["id"],
            "project_id": project.json()["id"],
            "requirement_id": requirement.json()["id"],
            "iteration_id": None,
            "title": "Scope validation case",
            "case_type": None,
            "test_scope": "functional_test",
            "test_scopes": ["functional_test", "system_test"],
            "default_tester_id": None,
            "latest_execute_time": None,
            "latest_result": None,
            "open_bug_count": 0,
        }
    ]
