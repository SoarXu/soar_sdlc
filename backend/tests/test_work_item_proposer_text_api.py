from uuid import uuid4

from fastapi.testclient import TestClient


def _create_project(client: TestClient, prefix: str) -> int:
    response = client.post("/api/v1/projects", json={"name": f"{prefix}-{uuid4().hex[:8]}"})
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _create_iteration(client: TestClient, project_id: int, prefix: str) -> int:
    response = client.post(
        "/api/v1/iterations",
        json={"project_ids": [project_id], "name": f"{prefix}-{uuid4().hex[:8]}"},
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_requirement_api_round_trips_free_text_proposer(client: TestClient):
    project_id = _create_project(client, "需求提出人文本")
    iteration_id = _create_iteration(client, project_id, "需求提出人迭代")

    created = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
            "title": "外部客户需求",
            "proposer": "客户代表 张三",
        },
    )

    assert created.status_code == 200, created.text
    assert created.json()["proposer"] == "客户代表 张三"

    updated = client.patch(
        f"/api/v1/requirements/{created.json()['id']}",
        json={"proposer": "合作方联系人 A-17"},
    )

    assert updated.status_code == 200, updated.text
    assert updated.json()["proposer"] == "合作方联系人 A-17"


def test_bug_api_round_trips_free_text_proposer(client: TestClient):
    project_id = _create_project(client, "Bug提出人文本")

    created = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "title": "外部反馈 Bug", "proposer": "现场用户 007"},
    )

    assert created.status_code == 200, created.text
    assert created.json()["proposer"] == "现场用户 007"

    updated = client.patch(
        f"/api/v1/bugs/{created.json()['id']}",
        json={"proposer": "匿名试用用户"},
    )

    assert updated.status_code == 200, updated.text
    assert updated.json()["proposer"] == "匿名试用用户"
