from datetime import datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.session import SessionLocal
from app.models.bug import Bug
from app.models.exception_rule import ExceptionRule
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


def test_exception_center_detects_owner_without_current_workflow_action_role(client: TestClient):
    project = client.post("/api/v1/projects", json={"name": f"Role eligibility {uuid4().hex[:8]}"}).json()
    developer_id, _ = _create_user("developer")
    owner_id, _ = _create_user("project_owner")
    _add_member(project["id"], developer_id, "developer")
    _add_member(project["id"], owner_id, "project_owner")
    invalid_task = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "title": "Wrong current role", "owner_id": developer_id},
    ).json()
    matching_task = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "title": "Matching current role", "owner_id": developer_id},
    ).json()
    owner_task = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "title": "Project owner action", "owner_id": owner_id},
    ).json()

    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == invalid_task["id"]).one()
        transition_query = db.query(WorkflowTransition).filter(
            WorkflowTransition.definition_id == task.workflow_definition_id,
            WorkflowTransition.from_state_id == task.current_state_id,
        )
        original_roles = {transition.id: transition.allowed_roles for transition in transition_query.all()}
        transition_query.update({"allowed_roles": "tester"}, synchronize_session=False)
        db.commit()
        invalid_refs = list_exception_refs(db, {project["id"]})

        transition_query.update({"allowed_roles": "developer"}, synchronize_session=False)
        db.commit()
        matching_refs = list_exception_refs(db, {project["id"]})

        transition_query.update({"allowed_roles": "project_owner"}, synchronize_session=False)
        db.commit()
        owner_refs = list_exception_refs(db, {project["id"]})
    finally:
        if "original_roles" in locals():
            for transition_id, allowed_roles in original_roles.items():
                db.query(WorkflowTransition).filter(WorkflowTransition.id == transition_id).update(
                    {"allowed_roles": allowed_roles}, synchronize_session=False
                )
            db.commit()
        db.close()

    def ineligible_ids(refs):
        return {item["id"] for item in refs if item["object_type"] == "task" and item["exception_key"] == "owner_ineligible"}

    assert invalid_task["id"] in ineligible_ids(invalid_refs)
    assert matching_task["id"] not in ineligible_ids(matching_refs)
    assert owner_task["id"] not in ineligible_ids(owner_refs)


def test_integrity_audit_distinguishes_verification_retry_from_true_activation(client: TestClient):
    project = client.post("/api/v1/projects", json={"name": f"Activation audit {uuid4().hex[:8]}"}).json()
    verification_bug = client.post("/api/v1/bugs", json={"project_id": project["id"], "title": "Verification retry"}).json()
    broken_activation = client.post("/api/v1/bugs", json={"project_id": project["id"], "title": "Broken activation"}).json()
    db = SessionLocal()
    try:
        verification_row = db.query(Bug).filter(Bug.id == verification_bug["id"]).one()
        broken_row = db.query(Bug).filter(Bug.id == broken_activation["id"]).one()
        verification_row.reopen_count = 1
        broken_row.reopen_count = 1
        db.add(_operation("bug", verification_row.id, verification_row.workflow_definition_id, verification_row.current_state_id, datetime.now(), "verification_failed"))
        activation = _operation("bug", broken_row.id, broken_row.workflow_definition_id, broken_row.current_state_id, datetime.now(), "activate")
        activation.reason = "reproduced"
        db.add(activation)
        db.commit()
        refs = list_exception_refs(db, {project["id"]})
    finally:
        db.close()
    missing_ids = {item["id"] for item in refs if item["exception_key"] == "missing_reactivation_audit"}
    assert verification_bug["id"] not in missing_ids
    assert broken_activation["id"] in missing_ids


def test_terminal_membership_integrity_is_checked_and_rules_cannot_disable_it(client: TestClient):
    project = client.post("/api/v1/projects", json={"name": f"Terminal integrity {uuid4().hex[:8]}"}).json()
    clean = client.post("/api/v1/tasks", json={"project_id": project["id"], "title": "Clean terminal"}).json()
    broken = client.post("/api/v1/tasks", json={"project_id": project["id"], "title": "Broken terminal"}).json()
    db = SessionLocal()
    try:
        integrity_rules = db.query(ExceptionRule).filter(ExceptionRule.exception_key == "iteration_history_inconsistent").all()
        if not integrity_rules:
            db.add(ExceptionRule(
                exception_key="iteration_history_inconsistent",
                label="Configurable rule must not control integrity",
                object_type="*",
                threshold_hours=99999,
                enabled=False,
            ))
            db.flush()
            integrity_rules = db.query(ExceptionRule).filter(ExceptionRule.exception_key == "iteration_history_inconsistent").all()
        original_rule_values = {rule.id: (rule.enabled, rule.threshold_hours) for rule in integrity_rules}
        for task_id in (clean["id"], broken["id"]):
            row = db.query(Task).filter(Task.id == task_id).one()
            row.current_state_id = _target_state_id(db, row.workflow_definition_id, "complete")
        db.add(WorkItemIterationHistory(object_type="task", object_id=broken["id"], iteration_id=99999999, enter_reason="illegal"))
        db.query(ExceptionRule).filter(ExceptionRule.exception_key == "iteration_history_inconsistent").update({"enabled": False, "threshold_hours": 99999})
        db.commit()
        refs = list_exception_refs(db, {project["id"]})
    finally:
        if "original_rule_values" in locals():
            for rule_id, (enabled, threshold_hours) in original_rule_values.items():
                db.query(ExceptionRule).filter(ExceptionRule.id == rule_id).update({"enabled": enabled, "threshold_hours": threshold_hours})
            db.commit()
        db.close()
    inconsistent_ids = {item["id"] for item in refs if item["exception_key"] == "iteration_history_inconsistent"}
    assert clean["id"] not in inconsistent_ids
    assert broken["id"] in inconsistent_ids


def test_owner_eligibility_uses_object_conditions_and_ignores_informational_actions(client: TestClient):
    project = client.post("/api/v1/projects", json={"name": f"Conditional role {uuid4().hex[:8]}"}).json()
    developer_id, _ = _create_user("developer")
    _add_member(project["id"], developer_id, "developer")
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "title": "Conditional bug fix", "task_type": "bug_fix", "owner_id": developer_id},
    ).json()
    db = SessionLocal()
    try:
        row = db.query(Task).filter(Task.id == task["id"]).one()
        row.current_state_id = _target_state_id(db, row.workflow_definition_id, "claim")
        transitions = db.query(WorkflowTransition).filter(
            WorkflowTransition.definition_id == row.workflow_definition_id,
            WorkflowTransition.from_state_id == row.current_state_id,
        ).all()
        original_roles = {transition.id: transition.allowed_roles for transition in transitions}
        for transition in transitions:
            transition.allowed_roles = "developer" if transition.action_key in {"complete", "add_information"} else "tester"
        db.commit()
        refs = list_exception_refs(db, {project["id"]})
    finally:
        if "original_roles" in locals():
            for transition_id, allowed_roles in original_roles.items():
                db.query(WorkflowTransition).filter(WorkflowTransition.id == transition_id).update({"allowed_roles": allowed_roles})
            db.commit()
        db.close()
    assert any(
        item["id"] == task["id"] and item["exception_key"] == "owner_ineligible"
        for item in refs
    )


def test_workbench_aggregates_integrity_details_and_enforces_project_scope(client: TestClient):
    project = client.post("/api/v1/projects", json={"name": f"Aggregate integrity {uuid4().hex[:8]}"}).json()
    viewer_id, viewer_token = _create_user("developer")
    invalid_owner_id, _ = _create_user("developer")
    _, outsider_token = _create_user("developer")
    _add_member(project["id"], viewer_id, "developer")
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "title": "Two integrity violations", "owner_id": invalid_owner_id},
    ).json()
    db = SessionLocal()
    try:
        db.add(WorkItemIterationHistory(object_type="task", object_id=task["id"], iteration_id=99999999, enter_reason="illegal"))
        db.commit()
    finally:
        db.close()

    visible = client.get(
        "/api/v1/dashboard/workbench",
        headers={"Authorization": f"Bearer {viewer_token}"},
    ).json()["exception_center"]["items"]
    hidden = client.get(
        "/api/v1/dashboard/workbench",
        headers={"Authorization": f"Bearer {outsider_token}"},
    ).json()["exception_center"]["items"]
    item = next(entry for entry in visible if entry["object_type"] == "task" and entry["id"] == task["id"])

    assert {"owner_ineligible", "iteration_history_inconsistent"} <= set(item["exception_keys"])
    assert {detail["exception_key"] for detail in item["exception_details"]} >= {
        "owner_ineligible", "iteration_history_inconsistent"
    }
    assert not any(entry["object_type"] == "task" and entry["id"] == task["id"] for entry in hidden)


def test_iteration_transfer_with_structural_history_but_no_operation_link_is_inconsistent(client: TestClient):
    project = client.post("/api/v1/projects", json={"name": f"Transfer audit {uuid4().hex[:8]}"}).json()
    task = client.post("/api/v1/tasks", json={"project_id": project["id"], "title": "Unlinked transfer"}).json()
    now = datetime.now()
    db = SessionLocal()
    try:
        row = db.query(Task).filter(Task.id == task["id"]).one()
        row.iteration_id = 2002
        db.add_all([
            WorkItemIterationHistory(
                object_type="task", object_id=row.id, iteration_id=2001, enter_reason="linked",
                entered_at=now - timedelta(hours=2), left_at=now - timedelta(hours=1), leave_reason="deferred",
            ),
            WorkItemIterationHistory(
                object_type="task", object_id=row.id, iteration_id=2002, enter_reason="deferred", entered_at=now,
            ),
        ])
        db.commit()
        refs = list_exception_refs(db, {project["id"]})
    finally:
        db.close()
    assert any(
        item["id"] == task["id"] and item["exception_key"] == "iteration_history_inconsistent"
        for item in refs
    )
