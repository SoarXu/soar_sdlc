from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.session import SessionLocal
from app.models.user import User


def test_proposer_text_does_not_make_item_created_by_that_user(client: TestClient):
    username = f"proposer.text.{uuid4().hex[:8]}"
    full_name = "外部提出人同名用户"
    db = SessionLocal()
    try:
        user = User(
            username=username,
            full_name=full_name,
            password_hash=get_password_hash("User123456"),
            is_active=True,
            is_system_admin=True,
        )
        db.add(user)
        db.commit()
    finally:
        db.close()

    project = client.post("/api/v1/projects", json={"name": f"提出人文本工作台-{uuid4().hex[:8]}"}).json()
    iteration = client.post(
        "/api/v1/iterations",
        json={"project_ids": [project["id"]], "name": f"提出人文本迭代-{uuid4().hex[:8]}"},
    ).json()
    started = client.post(
        f"/api/v1/workflow-runtime/iteration/{iteration['id']}/transition",
        json={"action_key": "start"},
    )
    assert started.status_code == 200, started.text
    created = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project["id"],
            "iteration_id": iteration["id"],
            "title": "不属于同名用户发起",
            "proposer": full_name,
        },
    )
    assert created.status_code == 200, created.text

    response = client.get(
        "/api/v1/dashboard/workbench",
        headers={"Authorization": f"Bearer {create_access_token(username)}"},
    )

    assert response.status_code == 200, response.text
    created_ids = {item["id"] for item in response.json()["created_by_me"]["items"]}
    assert created.json()["id"] not in created_ids
