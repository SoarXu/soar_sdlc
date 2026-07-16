from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.project_member import ProjectMember
from app.models.relation import ObjectRelation
from app.models.role import Role, UserRole
from app.models.task import Task
from app.models.user import User


def _create_user(full_name: str, role_key: str | None = None) -> tuple[int, str]:
    db = SessionLocal()
    try:
        user = User(
            username=f"linked_{uuid4().hex[:8]}",
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


def _add_member(project_id: int, user_id: int, project_role: str) -> None:
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


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_linked_task_creation_supports_all_sources_and_records_relation_and_audit(client: TestClient):
    handler_id, handler_token = _create_user("Linked Source Handler", "developer")
    project = client.post(
        "/api/v1/projects",
        json={"name": f"Linked Source Project {uuid4().hex[:8]}"},
    ).json()
    _add_member(project["id"], handler_id, "tester")
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "title": f"Linked Requirement {uuid4().hex[:8]}", "owner_id": handler_id},
    ).json()
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project["id"], "title": f"Linked Bug {uuid4().hex[:8]}", "owner_id": handler_id},
    ).json()
    test_case = client.post(
        "/api/v1/test-cases",
        json={"project_id": project["id"], "title": f"Linked Case {uuid4().hex[:8]}", "default_tester_id": handler_id},
        headers=_auth(handler_token),
    ).json()
    test_run = client.post(
        "/api/v1/test-runs",
        json={"project_id": project["id"], "name": f"Linked Run {uuid4().hex[:8]}", "test_owner_id": handler_id},
        headers=_auth(handler_token),
    ).json()
    sources = [
        ("requirement", requirement["id"], "requirement_implementation"),
        ("bug", bug["id"], "bug_fix"),
        ("test_case", test_case["id"], "test_support"),
        ("test_run", test_run["id"], "test_support"),
    ]

    created = []
    for source_type, source_id, expected_type in sources:
        response = client.post(
            "/api/v1/tasks/linked",
            json={
                "source_type": source_type,
                "source_id": source_id,
                "title": f"{source_type} linked task {uuid4().hex[:8]}",
                "description": "linked creation",
            },
            headers=_auth(handler_token),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["task_type"] == expected_type
        assert data["owner_id"] == handler_id
        assert data["status"] == "in_processing"
        assert data["creator_id"] == handler_id
        assert data["source_relations"] == [
            {"source_type": source_type, "source_id": source_id, "relation_type": "linked_task"}
        ]
        created.append((data, source_type, source_id))

    db = SessionLocal()
    try:
        for task, source_type, source_id in created:
            relation = db.query(ObjectRelation).filter(
                ObjectRelation.source_type == source_type,
                ObjectRelation.source_id == source_id,
                ObjectRelation.target_type == "task",
                ObjectRelation.target_id == task["id"],
                ObjectRelation.relation_type == "linked_task",
            ).one()
            assert relation.creator_id == handler_id
            audit = db.query(AuditLog).filter(
                AuditLog.object_type == "task",
                AuditLog.object_id == task["id"],
                AuditLog.action == "create_linked_task",
            ).one()
            assert audit.actor_id == handler_id
            assert audit.before_data == {"source_type": source_type, "source_id": source_id}
            assert audit.after_data["inherited_owner_id"] == handler_id
            assert audit.after_data["final_owner_id"] == handler_id
            assert audit.after_data["owner_overridden"] is False
    finally:
        db.close()


def test_linked_task_permissions_owner_inheritance_and_override(client: TestClient):
    source_owner_id, source_owner_token = _create_user("Linked Permission Owner", "developer")
    ordinary_id, ordinary_token = _create_user("Linked Permission Ordinary", "developer")
    project_owner_id, project_owner_token = _create_user("Linked Permission Project Owner", "project_owner")
    target_id, _ = _create_user("Linked Permission Target", "developer")
    project = client.post(
        "/api/v1/projects",
        json={"name": f"Linked Permission Project {uuid4().hex[:8]}", "owner_id": project_owner_id},
    ).json()
    for user_id, role in [(source_owner_id, "developer"), (ordinary_id, "developer"), (target_id, "developer")]:
        _add_member(project["id"], user_id, role)
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project["id"], "title": f"Permission Bug {uuid4().hex[:8]}", "owner_id": source_owner_id},
    ).json()

    rejected = client.post(
        "/api/v1/tasks/linked",
        json={"source_type": "bug", "source_id": bug["id"], "title": "forged linked task"},
        headers=_auth(ordinary_token),
    )
    override_without_reason = client.post(
        "/api/v1/tasks/linked",
        json={"source_type": "bug", "source_id": bug["id"], "title": "override without reason", "owner_id": target_id},
        headers=_auth(project_owner_token),
    )
    overridden = client.post(
        "/api/v1/tasks/linked",
        json={
            "source_type": "bug",
            "source_id": bug["id"],
            "title": "managed linked task",
            "owner_id": target_id,
            "override_reason": "specialist assignment",
        },
        headers=_auth(project_owner_token),
    )
    inherited = client.post(
        "/api/v1/tasks/linked",
        json={"source_type": "bug", "source_id": bug["id"], "title": "inherited linked task"},
        headers=_auth(source_owner_token),
    )

    assert rejected.status_code == 403
    assert override_without_reason.status_code == 422
    assert overridden.status_code == 201
    assert overridden.json()["owner_id"] == target_id
    assert inherited.status_code == 201
    assert inherited.json()["owner_id"] == source_owner_id
    db = SessionLocal()
    try:
        audit = db.query(AuditLog).filter(
            AuditLog.object_type == "task",
            AuditLog.object_id == overridden.json()["id"],
            AuditLog.action == "create_linked_task",
        ).one()
        assert audit.after_data["inherited_owner_id"] == source_owner_id
        assert audit.after_data["final_owner_id"] == target_id
        assert audit.after_data["owner_overridden"] is True
        assert audit.after_data["override_reason"] == "specialist assignment"
    finally:
        db.close()


def test_bug_close_checks_every_linked_task_without_mutating_blockers(client: TestClient):
    handler_id, handler_token = _create_user("Multi Task Bug Handler", "developer")
    project = client.post("/api/v1/projects", json={"name": f"Multi Task Bug Project {uuid4().hex[:8]}"}).json()
    _add_member(project["id"], handler_id, "developer")
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project["id"], "title": f"Multi Task Bug {uuid4().hex[:8]}", "owner_id": handler_id},
    ).json()
    first = client.post(
        "/api/v1/tasks/linked",
        json={"source_type": "bug", "source_id": bug["id"], "title": "finished linked task"},
        headers=_auth(handler_token),
    ).json()
    second = client.post(
        "/api/v1/tasks/linked",
        json={"source_type": "bug", "source_id": bug["id"], "title": "unfinished linked task"},
        headers=_auth(handler_token),
    ).json()
    db = SessionLocal()
    try:
        db.query(Task).filter(Task.id == first["id"]).update({"status": "completed"})
        db.query(Task).filter(Task.id == second["id"]).update({"status": "in_processing"})
        db.query(Task).filter(Task.id == first["id"]).update({"owner_id": handler_id})
        db.commit()
    finally:
        db.close()
    classified = client.post(
        f"/api/v1/workflow-runtime/bug/{bug['id']}/transition",
        json={"action_key": "confirm_bug_type", "payload": {"selected_values": {"bug_type": "design_as_intended"}}},
        headers=_auth(handler_token),
    )
    assert classified.status_code == 200
    assert classified.json()["status"] == "pending_verification"
    verified = client.post(
        f"/api/v1/workflow-runtime/bug/{bug['id']}/transition",
        json={"action_key": "verification_passed"},
        headers=_auth(handler_token),
    )
    assert verified.status_code == 200

    blocked = client.post(
        f"/api/v1/workflow-runtime/bug/{bug['id']}/transition",
        json={"action_key": "close"},
        headers=_auth(handler_token),
    )
    assert blocked.status_code == 400
    assert "1 unfinished linked task" in blocked.json()["detail"].lower()
    assert "unfinished linked task" in blocked.json()["detail"]
    assert client.get(f"/api/v1/bugs/{bug['id']}").json()["status"] == "verified"
    assert client.get(f"/api/v1/tasks/{second['id']}").json()["status"] == "in_processing"

    db = SessionLocal()
    try:
        db.query(Task).filter(Task.id == second["id"]).update({"status": "canceled"})
        db.commit()
    finally:
        db.close()
    closed = client.post(
        f"/api/v1/workflow-runtime/bug/{bug['id']}/transition",
        json={"action_key": "close"},
        headers=_auth(handler_token),
    )
    assert closed.status_code == 200
    detail = client.get(f"/api/v1/bugs/{bug['id']}").json()
    assert {item["id"] for item in detail["linked_tasks"]} == {first["id"], second["id"]}
