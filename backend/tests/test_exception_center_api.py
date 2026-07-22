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
from app.models.work_item_iteration_history import WorkItemIterationHistory
from app.models.workflow_definition import WorkflowTransition
from app.services.exception_center_service import list_exception_refs
from app.services.exception_center_service import _latest_state_time


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


def _target_state_id(db, definition_id: int, action_key: str) -> int:
    state_id = db.query(WorkflowTransition.to_state_id).filter(
        WorkflowTransition.definition_id == definition_id,
        WorkflowTransition.action_key == action_key,
    ).scalar()
    assert state_id is not None
    return state_id


def _operation(
    object_type: str,
    object_id: int,
    definition_id: int,
    state_id: int,
    entered_at: datetime,
    action: str = "enter_state",
):
    return StatusOperationLog(
        object_type=object_type,
        object_id=object_id,
        action=action,
        workflow_definition_id=definition_id,
        from_state_id=state_id,
        to_state_id=state_id,
        from_state_name="previous snapshot",
        to_state_name="current snapshot",
        from_status="legacy_previous",
        to_status="legacy_target",
        effective_time=entered_at,
    )


def test_latest_state_entry_time_matches_state_id_not_legacy_status(client: TestClient):
    project = client.post("/api/v1/projects", json={"name": f"State Time Project {uuid4().hex[:8]}"}).json()
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "title": "State time requirement"},
    ).json()
    entered_at = datetime(2026, 7, 12, 9, 30, 0)
    fallback = datetime(2026, 7, 1, 8, 0, 0)

    db = SessionLocal()
    try:
        db.add(
            StatusOperationLog(
                object_type="requirement",
                object_id=requirement["id"],
                action="enter_state",
                workflow_definition_id=requirement["workflow_definition_id"],
                from_state_id=requirement["current_state_id"],
                to_state_id=requirement["current_state_id"],
                from_state_name="旧快照",
                to_state_name="新快照",
                from_status="mismatched_previous",
                to_status="mismatched_target",
                effective_time=entered_at,
            )
        )
        db.commit()

        actual = _latest_state_time(
            db,
            "requirement",
            requirement["id"],
            requirement["current_state_id"],
            fallback,
        )
    finally:
        db.close()

    assert actual == entered_at


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
        requirement_row = db.query(Requirement).filter(Requirement.id == requirement["id"]).first()
        requirement_row.create_time = now - timedelta(hours=100)
        task_row = db.query(Task).filter(Task.id == task["id"]).first()
        task_row.current_state_id = _target_state_id(db, task_row.workflow_definition_id, "claim")
        task_row.create_time = now - timedelta(hours=100)
        action_by_status = {
            "fixing": "confirm_bug_type",
            "pending_verification": "submit_verification",
            "verified": "verification_passed",
            "closed": "close",
        }
        bug_rows = []
        for bug, (_, legacy_status, owner_id, _,) in zip(bugs, bug_payloads):
            bug_row = db.query(Bug).filter(Bug.id == bug["id"]).first()
            if legacy_status in action_by_status:
                bug_row.current_state_id = _target_state_id(
                    db,
                    bug_row.workflow_definition_id,
                    action_by_status[legacy_status],
                )
            bug_row.owner_id = owner_id
            bug_row.create_time = now - timedelta(hours=100)
            bug_rows.append(bug_row)
        db.query(Bug).filter(Bug.id == bugs[3]["id"]).update({"verify_result": "failed"})
        db.query(Bug).filter(Bug.id == bugs[4]["id"]).update({"reopen_count": 2})

        db.add(_operation(
            "requirement",
            requirement_row.id,
            requirement_row.workflow_definition_id,
            requirement_row.current_state_id,
            now - timedelta(hours=24),
        ))
        db.add(_operation(
            "task",
            task_row.id,
            task_row.workflow_definition_id,
            task_row.current_state_id,
            now - timedelta(hours=24),
        ))
        for index in range(6):
            row = bug_rows[index]
            db.add(_operation("bug", row.id, row.workflow_definition_id, row.current_state_id, now - timedelta(hours=24)))
        failed_row = bug_rows[3]
        db.add(_operation(
            "bug", failed_row.id, failed_row.workflow_definition_id, failed_row.current_state_id,
            now - timedelta(hours=1), "verification_failed",
        ))
        activated_row = bug_rows[4]
        db.add(_operation(
            "bug", activated_row.id, activated_row.workflow_definition_id, activated_row.current_state_id,
            now - timedelta(hours=1), "activate",
        ))
        fresh_row = bug_rows[6]
        db.add(_operation(
            "bug", fresh_row.id, fresh_row.workflow_definition_id, fresh_row.current_state_id,
            now - timedelta(hours=1),
        ))
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
        requirement_row = db.query(Requirement).filter(Requirement.id == requirement["id"]).first()
        requirement_row.current_state_id = _target_state_id(db, requirement_row.workflow_definition_id, "complete")
        completed_state_id = requirement_row.current_state_id
        db.commit()
        refs = list_exception_refs(db, {project["id"]}, now=now)
        stored_state_id = db.query(Requirement.current_state_id).filter(Requirement.id == requirement["id"]).scalar()
    finally:
        db.close()

    assert any(
        item["id"] == requirement["id"] and item["exception_key"] == "completed_requirement_active_bug"
        for item in refs
    )
    assert stored_state_id == completed_state_id
    assert bug["current_state_id"] is not None


def test_exception_center_reports_integrity_and_routing_violations_without_flagging_normal_backlog(client: TestClient):
    project = client.post("/api/v1/projects", json={"name": f"Integrity Project {uuid4().hex[:8]}"}).json()
    owner_id, _ = _create_user()
    _add_member(project["id"], owner_id)
    iteration = client.post(
        "/api/v1/iterations",
        json={"project_ids": [project["id"]], "name": f"Integrity iteration {uuid4().hex[:8]}"},
    ).json()
    ownerless_processing = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "title": "Ownerless processing", "owner_id": owner_id},
    ).json()
    invalid_owner = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "title": "Invalid owner", "owner_id": owner_id},
    ).json()
    history_mismatch = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "title": "History mismatch"},
    ).json()
    unaudited_reopen = client.post(
        "/api/v1/bugs",
        json={"project_id": project["id"], "title": "Unaudited reopen"},
    ).json()
    normal_backlog = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "title": "Normal unplanned backlog"},
    ).json()

    db = SessionLocal()
    try:
        ownerless_row = db.query(Task).filter(Task.id == ownerless_processing["id"]).one()
        ownerless_row.current_state_id = _target_state_id(db, ownerless_row.workflow_definition_id, "claim")
        ownerless_row.owner_id = None
        db.query(ProjectMember).filter(
            ProjectMember.project_id == project["id"], ProjectMember.user_id == owner_id
        ).delete()
        mismatch_row = db.query(Task).filter(Task.id == history_mismatch["id"]).one()
        mismatch_row.iteration_id = iteration["id"]
        db.add_all([
            WorkItemIterationHistory(object_type="task", object_id=mismatch_row.id, iteration_id=iteration["id"] + 999999, enter_reason="legacy"),
            WorkItemIterationHistory(object_type="task", object_id=mismatch_row.id, iteration_id=iteration["id"], enter_reason="legacy"),
        ])
        db.query(Bug).filter(Bug.id == unaudited_reopen["id"]).update({"reopen_count": 1})
        db.commit()
        refs = list_exception_refs(db, {project["id"]})
    finally:
        db.close()

    refs_by_key = {(item["object_type"], item["id"], item["exception_key"]) for item in refs}
    assert ("task", ownerless_processing["id"], "owner_required_missing") in refs_by_key
    assert ("task", invalid_owner["id"], "owner_ineligible") in refs_by_key
    assert ("task", history_mismatch["id"], "iteration_history_inconsistent") in refs_by_key
    assert ("bug", unaudited_reopen["id"], "missing_reactivation_audit") in refs_by_key
    assert not any(item["id"] == normal_backlog["id"] for item in refs)
