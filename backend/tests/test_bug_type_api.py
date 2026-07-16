from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.security import create_access_token, get_password_hash
from app.db.session import SessionLocal
from app.models.project_member import ProjectMember
from app.models.role import Role, UserRole
from app.models.user import User
from app.services.default_workflow_template_service import graph_for_object_type


EXPECTED_TYPE_KEYS = {
    "code_issue",
    "configuration_issue",
    "data_issue",
    "environment_issue",
    "requirement_issue",
    "design_as_intended",
    "duplicate_issue",
    "cannot_reproduce",
    "operation_issue",
}


def _create_user(full_name: str) -> tuple[int, str]:
    db = SessionLocal()
    try:
        user = User(
            username=f"bug.type.{uuid4().hex[:8]}",
            full_name=full_name,
            password_hash=get_password_hash("User123456"),
            is_active=True,
        )
        db.add(user)
        db.flush()
        role = db.query(Role).filter(Role.role_key == "developer").first()
        if not role:
            role = Role(role_key="developer", role_name="Developer", enabled=True, is_system=True)
            db.add(role)
            db.flush()
        db.add(UserRole(user_id=user.id, role_id=role.id))
        db.commit()
        return user.id, create_access_token(user.username)
    finally:
        db.close()


def _create_owned_bug(client: TestClient) -> tuple[dict, str]:
    project = client.post("/api/v1/projects", json={"name": f"Bug Type Project {uuid4().hex[:8]}"}).json()
    user_id, token = _create_user("Bug Type Handler")
    db = SessionLocal()
    try:
        db.add(ProjectMember(project_id=project["id"], user_id=user_id, project_role="developer"))
        db.commit()
    finally:
        db.close()
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project["id"], "title": f"Bug type {uuid4().hex[:8]}", "owner_id": user_id},
    ).json()
    return bug, token


def test_default_bug_type_dictionary_contains_prd_types(client: TestClient):
    response = client.get("/api/v1/bug-types")

    assert response.status_code == 200
    rows = response.json()
    assert {row["type_key"] for row in rows} == EXPECTED_TYPE_KEYS
    assert {row["default_target_status"] for row in rows} == {"fixing", "pending_verification"}
    assert next(row for row in rows if row["type_key"] == "code_issue")["is_real_bug"] is True
    assert next(row for row in rows if row["type_key"] == "design_as_intended")["is_real_bug"] is False
    assert next(row for row in rows if row["type_key"] == "environment_issue")["is_real_bug"] is None


def test_confirm_bug_type_action_uses_dictionary_options_and_records_metadata(client: TestClient):
    bug, token = _create_owned_bug(client)

    actions = client.get(
        f"/api/v1/workflow-runtime/bug/{bug['id']}/transitions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert actions.status_code == 200
    confirm = next(item for item in actions.json() if item["action_key"] == "confirm_bug_type")
    configured = next(item for item in graph_for_object_type("bug").transitions if item.action_key == "confirm_bug_type")
    assert configured.condition_config["route_dictionary"] == "bug_type"
    assert "routes" not in configured.condition_config
    field = next(item for item in confirm["form_config"]["fields"] if item["field"] == "bug_type")
    assert {item["value"] for item in field["options"]} == EXPECTED_TYPE_KEYS

    executed = client.post(
        f"/api/v1/workflow-runtime/bug/{bug['id']}/transition",
        json={"action_key": "confirm_bug_type", "payload": {"selected_values": {"bug_type": "code_issue"}}},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert executed.status_code == 200
    history = client.get(f"/api/v1/bugs/{bug['id']}/status-operations").json()
    assert history[-1]["selected_values"]["is_real_bug"] is True
    assert history[-1]["selected_values"]["dictionary_default_target_state_id"] == executed.json()["default_target_state_id"]


def test_disabled_bug_type_is_hidden_and_rejected_by_runtime(client: TestClient):
    assert client.get("/api/v1/bug-types").status_code == 200
    db = SessionLocal()
    try:
        db.execute(text("update bug_types set enabled = 0 where type_key = 'cannot_reproduce'"))
        db.commit()
    finally:
        db.close()
    try:
        bug, token = _create_owned_bug(client)
        actions = client.get(
            f"/api/v1/workflow-runtime/bug/{bug['id']}/transitions",
            headers={"Authorization": f"Bearer {token}"},
        ).json()
        confirm = next(item for item in actions if item["action_key"] == "confirm_bug_type")
        field = next(item for item in confirm["form_config"]["fields"] if item["field"] == "bug_type")
        assert "cannot_reproduce" not in {item["value"] for item in field["options"]}

        executed = client.post(
            f"/api/v1/workflow-runtime/bug/{bug['id']}/transition",
            json={"action_key": "confirm_bug_type", "payload": {"selected_values": {"bug_type": "cannot_reproduce"}}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert executed.status_code == 422
    finally:
        db = SessionLocal()
        try:
            db.execute(text("update bug_types set enabled = 1 where type_key = 'cannot_reproduce'"))
            db.commit()
        finally:
            db.close()
