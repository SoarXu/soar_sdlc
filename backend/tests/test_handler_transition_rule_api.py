from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.session import SessionLocal
from app.models.project_member import ProjectMember
from app.models.role import Role, UserRole
from app.models.user import User
from app.services.bug_service import BUG_RESOLUTIONS


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


def _valid_resolution() -> str:
    return sorted(BUG_RESOLUTIONS)[0]


def test_handler_transition_rule_crud(client: TestClient):
    config_id, _ = _create_configured_project(client)

    created = client.post(
        "/api/v1/handler-transition-rules",
        json={
            "config_id": config_id,
            "object_type": "bug",
            "action": "resolve",
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


def test_bug_resolve_and_verify_failed_apply_transition_rules(client: TestClient):
    config_id, project_id = _create_configured_project(client)
    developer_id, developer_token = _create_user("Bug Developer", "developer")
    tester_id, tester_token = _create_user("Bug Tester", "tester")
    _add_project_member(project_id, developer_id, "developer")
    _add_project_member(project_id, tester_id, "tester")
    for payload in [
        {
            "config_id": config_id,
            "object_type": "bug",
            "action": "resolve",
            "from_status": "fixing",
            "to_status": "verifying",
            "target_type": "project_role",
            "target_roles": "tester",
        },
        {
            "config_id": config_id,
            "object_type": "bug",
            "action": "verify_failed",
            "from_status": "verifying",
            "to_status": "reopened",
            "target_type": "project_role",
            "target_roles": "developer",
        },
    ]:
        response = client.post("/api/v1/handler-transition-rules", json=payload)
        assert response.status_code == 201
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "title": f"Transition Bug {uuid4().hex[:8]}", "owner_id": developer_id},
    ).json()

    fixing = client.post(
        f"/api/v1/bugs/{bug['id']}/start-fixing",
        json={},
        headers={"Authorization": f"Bearer {developer_token}"},
    )
    resolved = client.post(
        f"/api/v1/bugs/{bug['id']}/resolve",
        json={"resolution": _valid_resolution()},
        headers={"Authorization": f"Bearer {developer_token}"},
    )
    failed = client.post(
        f"/api/v1/bugs/{bug['id']}/verify-failed",
        json={"remark": "still failed"},
        headers={"Authorization": f"Bearer {tester_token}"},
    )

    assert fixing.status_code == 200
    assert resolved.status_code == 200
    assert resolved.json()["owner_id"] == tester_id
    assert failed.status_code == 200
    assert failed.json()["owner_id"] == developer_id
    history = client.get(f"/api/v1/bugs/{bug['id']}/status-operations").json()
    assert [item["action"] for item in history][-5:] == [
        "start_fixing",
        "resolve",
        "auto_assign",
        "verify_failed",
        "auto_assign",
    ]
    assert f"{developer_id} -> {tester_id}" in history[-3]["remark"]
    assert f"{tester_id} -> {developer_id}" in history[-1]["remark"]


def test_requirement_submit_validation_applies_transition_rule(client: TestClient):
    config_id, project_id = _create_configured_project(client)
    product_id, product_token = _create_user("Requirement Owner", "product_owner")
    tester_id, _ = _create_user("Requirement Tester", "tester")
    _add_project_member(project_id, product_id, "product_owner")
    _add_project_member(project_id, tester_id, "tester")
    response = client.post(
        "/api/v1/handler-transition-rules",
        json={
            "config_id": config_id,
            "object_type": "requirement",
            "action": "submit_validation",
            "from_status": "active",
            "to_status": "pending_validation",
            "target_type": "project_role",
            "target_roles": "tester",
        },
    )
    assert response.status_code == 201
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"Transition Requirement {uuid4().hex[:8]}", "owner_id": product_id},
    ).json()
    client.post(f"/api/v1/requirements/{requirement['id']}/activate", headers={"Authorization": f"Bearer {product_token}"})

    submitted = client.post(
        f"/api/v1/requirements/{requirement['id']}/complete",
        headers={"Authorization": f"Bearer {product_token}"},
    )

    assert submitted.status_code == 200
    assert submitted.json()["status"] == "pending_validation"
    assert submitted.json()["owner_id"] == tester_id


def test_missing_transition_rule_keeps_current_handler(client: TestClient):
    _, project_id = _create_configured_project(client)
    developer_id, developer_token = _create_user("Unchanged Developer", "developer")
    tester_id, _ = _create_user("Unused Tester", "tester")
    _add_project_member(project_id, developer_id, "developer")
    _add_project_member(project_id, tester_id, "tester")
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "title": f"No Rule Bug {uuid4().hex[:8]}", "owner_id": developer_id},
    ).json()

    client.post(f"/api/v1/bugs/{bug['id']}/start-fixing", json={}, headers={"Authorization": f"Bearer {developer_token}"})
    resolved = client.post(
        f"/api/v1/bugs/{bug['id']}/resolve",
        json={"resolution": _valid_resolution()},
        headers={"Authorization": f"Bearer {developer_token}"},
    )

    assert resolved.status_code == 200
    assert resolved.json()["owner_id"] == developer_id
