from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.security import create_access_token, get_password_hash
from app.db.session import SessionLocal
from app.models.bug import Bug
from app.models.project_member import ProjectMember
from app.models.role import Role, UserRole
from app.models.user import User
from app.models.workflow_definition import WorkflowTransition


def _create_project(client: TestClient) -> int:
    response = client.post("/api/v1/projects", json={"name": f"Bug API Project {uuid4().hex[:8]}"})
    assert response.status_code == 200
    return response.json()["id"]


def _create_user(role_key: str) -> tuple[int, str]:
    db = SessionLocal()
    try:
        role = db.query(Role).filter(Role.role_key == role_key).first()
        if not role:
            role = Role(role_key=role_key, role_name=role_key, enabled=True, is_system=True)
            db.add(role)
            db.flush()
        username = f"bug_reactivate_{uuid4().hex[:8]}"
        user = User(
            username=username,
            full_name=username,
            password_hash=get_password_hash("User123456"),
            is_active=True,
        )
        db.add(user)
        db.flush()
        db.add(UserRole(user_id=user.id, role_id=role.id))
        db.commit()
        return user.id, create_access_token(username)
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


def _create_iteration(client: TestClient, project_id: int, name: str, *, active: bool) -> int:
    iteration = client.post("/api/v1/iterations", json={"project_ids": [project_id], "name": name})
    assert iteration.status_code == 200
    iteration_id = iteration.json()["id"]
    if active:
        started = client.post(
            f"/api/v1/workflow-runtime/iteration/{iteration_id}/transition",
            json={"action_key": "start"},
        )
        assert started.status_code == 200
    return iteration_id


def _set_bug_closed(bug_id: int) -> None:
    db = SessionLocal()
    try:
        bug = db.query(Bug).filter(Bug.id == bug_id).one()
        closed_state_id = db.query(WorkflowTransition.to_state_id).filter(
            WorkflowTransition.definition_id == bug.workflow_definition_id,
            WorkflowTransition.action_key.in_(("close", "void_close")),
        ).first()[0]
        bug.current_state_id = closed_state_id
        db.commit()
    finally:
        db.close()


def _create_bug(client: TestClient, **overrides) -> dict:
    payload = {
        "project_id": _create_project(client),
        "title": f"Bug API {uuid4().hex[:8]}",
    }
    payload.update(overrides)
    response = client.post("/api/v1/bugs", json=payload)
    assert response.status_code == 200
    assert response.json()["status_name"] == "待处理"
    return response.json()


def test_bug_crud_keeps_status_changes_on_workflow_runtime(client: TestClient):
    bug = _create_bug(client)

    detail = client.get(f"/api/v1/bugs/{bug['id']}")
    updated = client.patch(f"/api/v1/bugs/{bug['id']}", json={"title": "Updated bug title", "status": "closed"})
    history = client.get(f"/api/v1/bugs/{bug['id']}/status-operations")

    assert detail.status_code == 200
    assert updated.status_code == 422
    unchanged = client.get(f"/api/v1/bugs/{bug['id']}").json()
    assert unchanged["title"] == bug["title"]
    assert unchanged["status_name"] == "待处理"
    assert history.status_code == 200


def test_legacy_bug_status_endpoints_are_removed(client: TestClient):
    bug = _create_bug(client)

    for path in [
        "start-fixing",
        "resolve",
        "verify-passed",
        "verify-failed",
        "suspend",
        "close",
        "activate",
    ]:
        response = client.post(f"/api/v1/bugs/{bug['id']}/{path}", json={})
        assert response.status_code == 404


def test_bug_create_and_update_reject_closed_iteration(client: TestClient):
    project_id = _create_project(client)
    iteration = client.post(
        "/api/v1/iterations",
        json={"project_ids": [project_id], "name": f"Completed Iteration {uuid4().hex[:8]}"},
    )
    assert iteration.status_code == 200
    iteration_id = iteration.json()["id"]
    started = client.post(
        f"/api/v1/workflow-runtime/iteration/{iteration_id}/transition",
        json={"action_key": "start"},
    )
    completed = client.post(
        f"/api/v1/workflow-runtime/iteration/{iteration_id}/transition",
        json={"action_key": "complete"},
    )
    assert started.status_code == 200
    assert completed.status_code == 200

    created_with_finished_iteration = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": f"Bug {uuid4().hex[:8]}"},
    )
    bug = client.post("/api/v1/bugs", json={"project_id": project_id, "title": f"Bug {uuid4().hex[:8]}"})
    updated_with_finished_iteration = client.patch(
        f"/api/v1/bugs/{bug.json()['id']}",
        json={"iteration_id": iteration_id},
    )

    assert created_with_finished_iteration.status_code == 409
    assert created_with_finished_iteration.json()["detail"]["code"] == "ITERATION_NOT_MUTABLE"
    assert bug.status_code == 200
    assert updated_with_finished_iteration.status_code == 409
    assert updated_with_finished_iteration.json()["detail"]["code"] == "ITERATION_NOT_MUTABLE"


def test_closed_bug_reactivates_into_active_iteration_and_retains_eligible_handler(client: TestClient):
    reporter_id, reporter_token = _create_user("developer")
    handler_id, _ = _create_user("developer")
    project_id = _create_project(client)
    _add_member(project_id, reporter_id, "developer")
    _add_member(project_id, handler_id, "developer")
    source_iteration_id = _create_iteration(client, project_id, "Closed source iteration", active=True)
    target_iteration_id = _create_iteration(client, project_id, "Active target iteration", active=True)
    bug = client.post(
        "/api/v1/bugs",
        json={
            "project_id": project_id,
            "iteration_id": source_iteration_id,
            "title": "Recurring bug",
            "owner_id": handler_id,
            "reporter_id": reporter_id,
        },
        headers={"Authorization": f"Bearer {reporter_token}"},
    ).json()
    _set_bug_closed(bug["id"])
    completed = client.post(
        f"/api/v1/workflow-runtime/iteration/{source_iteration_id}/transition",
        json={"action_key": "complete"},
    )
    assert completed.status_code == 200

    actions = client.get(
        f"/api/v1/workflow-runtime/bug/{bug['id']}/transitions",
        headers={"Authorization": f"Bearer {reporter_token}"},
    ).json()
    activate_action = next(item for item in actions if item["action_key"] == "activate")
    target_field = next(
        field for field in activate_action["form_config"]["fields"] if field["field"] == "target_iteration_id"
    )
    assert target_field["required"] is True
    assert {option["value"] for option in target_field["options"]} == {target_iteration_id}
    assert activate_action["form_config"]["allow_manual_owner"] is True
    assert activate_action["ui_config"]["recommended_owner_id"] == handler_id

    reactivated = client.post(
        f"/api/v1/workflow-runtime/bug/{bug['id']}/transition",
        json={
            "action_key": "activate",
            "next_owner_id": handler_id,
            "payload": {"reason": "Issue reproduced", "target_iteration_id": target_iteration_id},
        },
        headers={"Authorization": f"Bearer {reporter_token}"},
    )

    assert reactivated.status_code == 200, reactivated.text
    assert reactivated.json()["id"] == bug["id"]
    assert reactivated.json()["owner_id"] == handler_id
    handler_routing = reactivated.json()["selected_values"]["handler_routing"]
    assert handler_routing["source_rule"] == "eligible_original_handler"
    assert handler_routing["manual_override"] is False
    detail = client.get(f"/api/v1/bugs/{bug['id']}").json()
    assert detail["iteration_id"] == target_iteration_id
    assert detail["reopen_count"] == 1
    assert [row["iteration_id"] for row in detail["iteration_history"]] == [source_iteration_id, target_iteration_id]
    assert detail["iteration_history"][0]["status_name_at_leave"] == "已关闭"
    source_detail = client.get(f"/api/v1/iterations/{source_iteration_id}/detail").json()
    historical_bug = next(item for item in source_detail["historical_bugs"] if item["id"] == bug["id"])
    assert historical_bug["status_name_at_leave"] == "已关闭"
    assert historical_bug["current_iteration_id"] == target_iteration_id
    assert historical_bug["leave_reason"] == "reactivated"

    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                "select iteration_id, enter_reason, leave_reason, left_at, operation_log_id "
                "from work_item_iteration_history where object_type = 'bug' and object_id = :object_id "
                "order by id"
            ),
            {"object_id": bug["id"]},
        ).all()
        assert [row.iteration_id for row in rows] == [source_iteration_id, target_iteration_id]
        assert rows[0].leave_reason == "reactivated"
        assert rows[0].left_at is not None
        assert rows[1].enter_reason == "reactivated"
        assert rows[1].left_at is None
        assert rows[0].operation_log_id is not None
        assert rows[1].operation_log_id == rows[0].operation_log_id
    finally:
        db.close()


def test_bug_reactivation_drops_original_handler_who_is_not_a_project_member(client: TestClient):
    reporter_id, reporter_token = _create_user("developer")
    former_handler_id, _ = _create_user("developer")
    project_id = _create_project(client)
    _add_member(project_id, reporter_id, "developer")
    source_iteration_id = _create_iteration(client, project_id, "Former handler source", active=True)
    target_iteration_id = _create_iteration(client, project_id, "Former handler target", active=True)
    bug = client.post(
        "/api/v1/bugs",
        json={
            "project_id": project_id,
            "iteration_id": source_iteration_id,
            "title": "Bug owned by former member",
            "owner_id": former_handler_id,
            "reporter_id": reporter_id,
        },
        headers={"Authorization": f"Bearer {reporter_token}"},
    ).json()
    _set_bug_closed(bug["id"])
    assert client.post(
        f"/api/v1/workflow-runtime/iteration/{source_iteration_id}/transition",
        json={"action_key": "complete"},
    ).status_code == 200

    actions = client.get(
        f"/api/v1/workflow-runtime/bug/{bug['id']}/transitions",
        headers={"Authorization": f"Bearer {reporter_token}"},
    ).json()
    activate_action = next(item for item in actions if item["action_key"] == "activate")
    assert activate_action["ui_config"]["original_owner_id"] == former_handler_id
    assert activate_action["ui_config"]["original_owner_eligible"] is False
    assert activate_action["ui_config"]["recommended_owner_id"] is None

    reactivated = client.post(
        f"/api/v1/workflow-runtime/bug/{bug['id']}/transition",
        json={
            "action_key": "activate",
            "payload": {"reason": "Former handler left", "target_iteration_id": target_iteration_id},
        },
        headers={"Authorization": f"Bearer {reporter_token}"},
    )

    assert reactivated.status_code == 200, reactivated.text
    assert reactivated.json()["owner_id"] is None
