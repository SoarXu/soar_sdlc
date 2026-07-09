from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.session import SessionLocal
from app.models.project_member import ProjectMember
from app.models.role import Role, UserRole
from app.models.user import User


def _create_user(full_name: str, role_key: str | None = None) -> tuple[int, str]:
    db = SessionLocal()
    try:
        user = User(
            username=f"transition_{uuid4().hex[:8]}",
            full_name=full_name,
            password_hash=get_password_hash("User123456"),
            is_active=True,
        )
        db.add(user)
        db.flush()
        if role_key:
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


def _add_project_member(project_id: int, user_id: int, project_role: str, sort_order: int = 0) -> None:
    db = SessionLocal()
    try:
        db.add(
            ProjectMember(
                project_id=project_id,
                user_id=user_id,
                project_role=project_role,
                sort_order=sort_order,
                is_workbench_participant=True,
            )
        )
        db.commit()
    finally:
        db.close()


def _create_configured_project(client: TestClient) -> tuple[int, int]:
    config = client.post(
        "/api/v1/assignee-rule-configs",
        json={
            "name": f"Transition Rule Config {uuid4().hex[:8]}",
            "requirement_owner_roles": "product_owner",
            "task_owner_roles": "developer",
            "test_case_tester_roles": "tester",
            "test_run_owner_roles": "tester",
            "bug_owner_roles": "developer",
        },
    )
    assert config.status_code == 201
    project = client.post(
        "/api/v1/projects",
        json={"name": f"Transition Project {uuid4().hex[:8]}", "assignee_rule_config_id": config.json()["id"]},
    )
    assert project.status_code == 200
    return config.json()["id"], project.json()["id"]


def test_handler_transition_rule_crud(client: TestClient):
    config_id, _ = _create_configured_project(client)

    created = client.post(
        "/api/v1/handler-transition-rules",
        json={
            "config_id": config_id,
            "object_type": "bug",
            "action": "submit_verification",
            "from_status": "fixing",
            "to_status": "verifying",
            "target_type": "project_role",
            "target_roles": "test_lead,tester",
            "fallback_type": "keep_current",
            "enabled": True,
        },
    )

    assert created.status_code == 201
    data = created.json()
    assert data["config_id"] == config_id
    assert data["target_roles"] == "test_lead,tester"

    listed = client.get(f"/api/v1/handler-transition-rules?config_id={config_id}")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [data["id"]]

    updated = client.patch(
        f"/api/v1/handler-transition-rules/{data['id']}",
        json={"target_roles": "tester", "enabled": False},
    )
    assert updated.status_code == 200
    assert updated.json()["target_roles"] == "tester"
    assert updated.json()["enabled"] is False

    deleted = client.delete(f"/api/v1/handler-transition-rules/{data['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/handler-transition-rules?config_id={config_id}").json()[0]["enabled"] is False
