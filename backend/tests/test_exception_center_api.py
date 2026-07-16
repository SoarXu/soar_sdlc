from datetime import datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.session import SessionLocal
from app.models.bug import Bug
from app.models.project_member import ProjectMember
from app.models.requirement import Requirement
from app.models.role import Role, UserRole
from app.models.status_operation import StatusOperationLog
from app.models.task import Task
from app.models.user import User
from app.services.exception_center_service import list_exception_refs


EXPECTED_KEYS = {
    "unassigned_timeout",
    "pending_timeout",
    "fixing_timeout",
    "pending_verification_timeout",
    "verified_not_closed",
    "verification_failed",
    "repeated_activation",
    "high_priority_unprocessed",
}


def _create_user(role_key: str = "developer") -> tuple[int, str]:
    db = SessionLocal()
    try:
        user = User(
            username=f"exception_{uuid4().hex[:8]}",
            full_name="Exception User",
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


def _add_member(project_id: int, user_id: int, role: str = "developer") -> None:
    db = SessionLocal()
    try:
        db.add(ProjectMember(project_id=project_id, user_id=user_id, project_role=role, is_workbench_participant=True))
        db.commit()
    finally:
        db.close()


def _operation(object_type: str, object_id: int, status: str, entered_at: datetime, action: str = "enter_state"):
    return StatusOperationLog(
        object_type=object_type,
        object_id=object_id,
        action=action,
        from_status="previous",
        to_status=status,
        effective_time=entered_at,
    )


def test_exception_rule_defaults_and_admin_update(client: TestClient):
    listed = client.get("/api/v1/exception-rules")
    assert listed.status_code == 200
    rules = listed.json()
    assert EXPECTED_KEYS <= {item["exception_key"] for item in rules}

    target = next(item for item in rules if item["exception_key"] == "fixing_timeout" and item["object_type"] == "bug")
    updated = client.patch(f"/api/v1/exception-rules/{target['id']}", json={"threshold_hours": 12})
    assert updated.status_code == 200
    assert updated.json()["threshold_hours"] == 12

    user_id, token = _create_user()
    denied = client.patch(
        f"/api/v1/exception-rules/{target['id']}",
        json={"threshold_hours": 8},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert user_id
    assert denied.status_code == 403


def test_exception_center_covers_eight_types_and_uses_latest_state_entry_time(client: TestClient):
    now = datetime(2026, 7, 13, 12, 0, 0)
    user_id, _ = _create_user()
    project = client.post("/api/v1/projects", json={"name": f"Exception Project {uuid4().hex[:8]}"}).json()
    _add_member(project["id"], user_id)

    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "title": "Unassigned exception", "priority": "3"},
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "title": "Processing exception", "owner_id": user_id},
    ).json()
    bug_payloads = [
        ("Fixing exception", "fixing", user_id, "3"),
        ("Verification timeout", "pending_verification", user_id, "3"),
        ("Verified exception", "verified", user_id, "3"),
        ("Verification failed", "pending_handling", user_id, "3"),
        ("Repeated activation", "closed", user_id, "3"),
        ("High priority", "pending_handling", None, "1"),
        ("Fresh fixing state", "fixing", user_id, "3"),
    ]
    bugs = []
    for title, _, owner_id, priority in bug_payloads:
        bugs.append(
            client.post(
                "/api/v1/bugs",
                json={"project_id": project["id"], "title": title, "owner_id": owner_id, "priority": priority},
            ).json()
        )

    db = SessionLocal()
    try:
        db.query(Requirement).filter(Requirement.id == requirement["id"]).update({"create_time": now - timedelta(hours=100)})
        db.query(Task).filter(Task.id == task["id"]).update({"status": "in_processing", "create_time": now - timedelta(hours=100)})
        for bug, (_, status, owner_id, _,) in zip(bugs, bug_payloads):
            db.query(Bug).filter(Bug.id == bug["id"]).update(
                {"status": status, "owner_id": owner_id, "create_time": now - timedelta(hours=100)}
            )
        db.query(Bug).filter(Bug.id == bugs[3]["id"]).update({"verify_result": "failed"})
        db.query(Bug).filter(Bug.id == bugs[4]["id"]).update({"reopen_count": 2})

        db.add(_operation("requirement", requirement["id"], "pending_assignment", now - timedelta(hours=24)))
        db.add(_operation("task", task["id"], "in_processing", now - timedelta(hours=24)))
        for index in range(6):
            db.add(_operation("bug", bugs[index]["id"], bug_payloads[index][1], now - timedelta(hours=24)))
        db.add(_operation("bug", bugs[3]["id"], "pending_handling", now - timedelta(hours=1), "verification_failed"))
        db.add(_operation("bug", bugs[4]["id"], "closed", now - timedelta(hours=1), "activate"))
        db.add(_operation("bug", bugs[6]["id"], "fixing", now - timedelta(hours=1)))
        db.commit()

        refs = list_exception_refs(db, {project["id"]}, now=now)
    finally:
        db.close()

    assert EXPECTED_KEYS <= {item["exception_key"] for item in refs}
    assert not any(
        item["id"] == bugs[6]["id"] and item["exception_key"] == "fixing_timeout"
        for item in refs
    )
    timed = next(item for item in refs if item["exception_key"] == "pending_verification_timeout")
    assert timed["threshold_hours"] == 24
    assert timed["overdue_hours"] == 0
    assert timed["entered_at"].startswith("2026-07-12T12:00:00")


def test_completed_requirement_with_active_bug_is_reported_without_reopening(client: TestClient):
    now = datetime(2026, 7, 13, 12, 0, 0)
    project = client.post("/api/v1/projects", json={"name": f"Completed Requirement Project {uuid4().hex[:8]}"}).json()
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "title": "Completed parent"},
    ).json()
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project["id"], "requirement_id": requirement["id"], "title": "Active child bug"},
    ).json()
    db = SessionLocal()
    try:
        db.query(Requirement).filter(Requirement.id == requirement["id"]).update({"status": "completed"})
        refs = list_exception_refs(db, {project["id"]}, now=now)
        stored_status = db.query(Requirement.status).filter(Requirement.id == requirement["id"]).scalar()
    finally:
        db.close()

    assert any(
        item["id"] == requirement["id"] and item["exception_key"] == "completed_requirement_active_bug"
        for item in refs
    )
    assert stored_status == "completed"
    assert bug["status"] != "closed"
