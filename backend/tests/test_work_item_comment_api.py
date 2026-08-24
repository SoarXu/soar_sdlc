from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.session import SessionLocal
from app.models.project_member import ProjectMember
from app.models.role import RoleCapability
from app.models.user import User


def _create_user(full_name: str) -> tuple[int, str]:
    db = SessionLocal()
    try:
        user = User(
            username=f"comment_{uuid4().hex[:8]}",
            full_name=full_name,
            password_hash=get_password_hash("User123456"),
            is_active=True,
        )
        db.add(user)
        db.flush()
        db.commit()
        return user.id, create_access_token(user.username)
    finally:
        db.close()


def _add_project_member(project_id: int, user_id: int, capability: str = "developer") -> None:
    db = SessionLocal()
    try:
        role_id = db.query(RoleCapability.role_id).filter(RoleCapability.capability == capability).scalar()
        assert role_id is not None, f"Missing role capability: {capability}"
        db.add(
            ProjectMember(
                project_id=project_id,
                user_id=user_id,
                role_id=role_id,
                is_workbench_participant=True,
            )
        )
        db.commit()
    finally:
        db.close()


def test_create_comment_with_mentions_and_auto_watch(client: TestClient):
    author_id, author_token = _create_user("Comment Author")
    mentioned_id, mentioned_token = _create_user("Mentioned User")
    project = client.post("/api/v1/projects", json={"name": f"Comment Project {uuid4().hex[:8]}"}).json()
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project["id"], "title": f"Comment Bug {uuid4().hex[:8]}"},
    ).json()
    _add_project_member(project["id"], author_id)
    _add_project_member(project["id"], mentioned_id)

    created = client.post(
        "/api/v1/work-item-comments",
        json={
            "object_type": "bug",
            "object_id": bug["id"],
            "body": "please verify",
            "mentioned_user_ids": [mentioned_id],
        },
        headers={"Authorization": f"Bearer {author_token}"},
    )

    assert created.status_code == 201
    assert created.json()["author_id"] == author_id
    assert created.json()["mentioned_user_ids"] == [mentioned_id]

    listed = client.get(
        f"/api/v1/work-item-comments?object_type=bug&object_id={bug['id']}",
        headers={"Authorization": f"Bearer {author_token}"},
    )

    assert listed.status_code == 200
    assert listed.json()["items"][0]["id"] == created.json()["id"]
    assert listed.json()["items"][0]["body"] == "please verify"

    watch_state = client.get(
        f"/api/v1/object-watches?object_type=bug&object_id={bug['id']}",
        headers={"Authorization": f"Bearer {mentioned_token}"},
    )

    assert watch_state.status_code == 200
    assert watch_state.json()["watched"] is True
    assert mentioned_id in {item["user_id"] for item in watch_state.json()["watchers"]}


def test_comment_mention_users_are_limited_to_work_item_project_members(client: TestClient):
    author_id, author_token = _create_user("Comment Mention Author")
    member_id, _ = _create_user("Comment Mention Member")
    outsider_id, _ = _create_user("Comment Mention Outsider")
    project = client.post("/api/v1/projects", json={"name": f"Mention Scope Project {uuid4().hex[:8]}"}).json()
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project["id"], "title": f"Mention Scope Bug {uuid4().hex[:8]}"},
    ).json()
    _add_project_member(project["id"], author_id)
    _add_project_member(project["id"], member_id)

    response = client.get(
        f"/api/v1/work-item-comments/mention-users?object_type=bug&object_id={bug['id']}",
        headers={"Authorization": f"Bearer {author_token}"},
    )

    assert response.status_code == 200
    assert {user["id"] for user in response.json()} == {author_id, member_id}
    assert outsider_id not in {user["id"] for user in response.json()}
