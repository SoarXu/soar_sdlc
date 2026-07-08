from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.session import SessionLocal
from app.models.project_member import ProjectMember
from app.models.role import Role, UserRole
from app.models.user import User


def _create_user(full_name: str, role_key: str = "developer") -> tuple[int, str]:
    db = SessionLocal()
    try:
        user = User(
            username=f"notify_{uuid4().hex[:8]}",
            full_name=full_name,
            password_hash=get_password_hash("User123456"),
            is_active=True,
        )
        db.add(user)
        db.flush()
        role = db.query(Role).filter(Role.role_key == role_key).first()
        if not role:
            role = Role(role_key=role_key, role_name=role_key, enabled=True, is_system=True)
            db.add(role)
            db.flush()
        db.add(UserRole(user_id=user.id, role_id=role.id))
        db.commit()
        return user.id, create_access_token(user.username)
    finally:
        db.close()


def _add_project_member(project_id: int, user_id: int, project_role: str = "developer") -> None:
    db = SessionLocal()
    try:
        db.add(
            ProjectMember(
                project_id=project_id,
                user_id=user_id,
                project_role=project_role,
                is_workbench_participant=True,
            )
        )
        db.commit()
    finally:
        db.close()


def test_comment_mentions_create_notifications(client: TestClient):
    author_id, author_token = _create_user("Notifier Author")
    mentioned_id, mentioned_token = _create_user("Notifier Mentioned")
    project = client.post("/api/v1/projects", json={"name": f"Notify Project {uuid4().hex[:8]}"}).json()
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "title": f"Notify Task {uuid4().hex[:8]}"},
    ).json()
    _add_project_member(project["id"], author_id)
    _add_project_member(project["id"], mentioned_id)

    comment = client.post(
        "/api/v1/work-item-comments",
        json={
            "object_type": "task",
            "object_id": task["id"],
            "body": "need your confirmation",
            "mentioned_user_ids": [mentioned_id],
        },
        headers={"Authorization": f"Bearer {author_token}"},
    )
    assert comment.status_code == 201

    notifications = client.get(
        "/api/v1/notifications",
        headers={"Authorization": f"Bearer {mentioned_token}"},
    )

    assert notifications.status_code == 200
    assert notifications.json()[0]["receiver_id"] == mentioned_id
    assert notifications.json()[0]["category"] == "mention"
    assert notifications.json()[0]["object_type"] == "task"
    assert notifications.json()[0]["object_id"] == task["id"]
    assert notifications.json()[0]["source_type"] == "work_item_comment"
    assert notifications.json()[0]["source_id"] == comment.json()["id"]
