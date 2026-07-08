from uuid import uuid4

from fastapi.testclient import TestClient


def _create_config(client: TestClient) -> int:
    response = client.post(
        "/api/v1/assignee-rule-configs",
        json={
            "name": f"Cleanup Config {uuid4().hex[:8]}",
            "requirement_owner_roles": "",
            "task_owner_roles": "",
            "test_case_tester_roles": "tester",
            "test_run_owner_roles": "tester",
            "bug_owner_roles": "",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_handler_transition_matrix_api_is_not_public(client: TestClient):
    config_id = _create_config(client)

    loaded = client.get(f"/api/v1/handler-transition-matrix?config_id={config_id}")
    saved = client.put("/api/v1/handler-transition-matrix", json={"config_id": config_id, "items": []})
    templated = client.post("/api/v1/handler-transition-matrix/apply-template", json={"config_id": config_id})

    assert loaded.status_code == 404
    assert saved.status_code == 404
    assert templated.status_code == 404


def test_handler_transition_rules_reject_matrix_rule_type(client: TestClient):
    config_id = _create_config(client)

    response = client.post(
        "/api/v1/handler-transition-rules",
        json={
            "config_id": config_id,
            "rule_type": "matrix",
            "object_type": "bug",
            "action": "*",
            "to_status": "open",
            "target_type": "project_role",
            "target_roles": "developer",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Unknown rule type"
