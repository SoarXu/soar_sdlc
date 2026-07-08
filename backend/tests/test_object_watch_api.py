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
            username=f"watch_{uuid4().hex[:8]}",
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


def test_manual_watch_and_unwatch_supported_work_item(client: TestClient):
    user_id, token = _create_user("Watch User")
    project = client.post("/api/v1/projects", json={"name": f"Watch Project {uuid4().hex[:8]}"}).json()
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "title": f"Watch Requirement {uuid4().hex[:8]}"},
    ).json()
    _add_project_member(project["id"], user_id)

    watched = client.post(
        "/api/v1/object-watches",
        json={"object_type": "requirement", "object_id": requirement["id"]},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert watched.status_code == 200
    assert watched.json()["watched"] is True
    assert watched.json()["watcher_count"] == 1
    assert watched.json()["watchers"][0]["user_id"] == user_id

    detail = client.get(
        f"/api/v1/object-watches?object_type=requirement&object_id={requirement['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert detail.status_code == 200
    assert detail.json()["watched"] is True
    assert detail.json()["watcher_count"] == 1

    unwatched = client.delete(
        f"/api/v1/object-watches?object_type=requirement&object_id={requirement['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert unwatched.status_code == 204
    after = client.get(
        f"/api/v1/object-watches?object_type=requirement&object_id={requirement['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert after.status_code == 200
    assert after.json()["watched"] is False
    assert after.json()["watcher_count"] == 0
