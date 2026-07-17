from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.session import SessionLocal
from app.models.bug import Bug
from app.models.iteration import Iteration
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.requirement import Requirement
from app.models.role import Role, UserRole
from app.models.task import Task
from app.models.user import User
from app.models.workflow_definition import WorkflowState, WorkflowTransition
from app.views.workflow_definition_view import WorkflowTemplateState, WorkflowTemplateTransition


def test_template_build_contract_uses_request_local_refs_not_status_columns():
    assert set(WorkflowTemplateState.model_fields) >= {"ref", "status_name"}
    assert "status_key" not in WorkflowTemplateState.model_fields
    assert set(WorkflowTemplateTransition.model_fields) >= {"from_ref", "to_ref"}
    assert "from_status" not in WorkflowTemplateTransition.model_fields
    assert "to_status" not in WorkflowTemplateTransition.model_fields


def _create_user(full_name: str, role_key: str) -> tuple[int, str]:
    db = SessionLocal()
    try:
        user = User(
            username=f"default_template_{uuid4().hex[:8]}",
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


def _add_project_member(project_id: int, user_id: int, project_role: str) -> None:
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


def _state_id_for_status(db, item, status: str) -> int:
    action_by_status = {
        "in_processing": "claim",
        "pending_confirmation": "submit_confirmation",
        "completed": "complete",
        "canceled": "cancel",
        "fixing": "confirm_bug_type",
        "pending_verification": "submit_verification",
        "verified": "verification_passed",
        "closed": "close",
        "active": "start",
        "paused": "suspend",
    }
    if status in {"pending_assignment", "pending_handling", "planning"}:
        state_ids = {
            value
            for value, in db.query(WorkflowState.id).filter(
                WorkflowState.definition_id == item.workflow_definition_id,
                WorkflowState.category == "start",
            ).all()
        }
    else:
        action_key = action_by_status[status]
        state_ids = {
            value
            for value, in db.query(WorkflowTransition.to_state_id).filter(
                WorkflowTransition.definition_id == item.workflow_definition_id,
                WorkflowTransition.action_key == action_key,
            ).all()
        }
    assert len(state_ids) == 1
    return next(iter(state_ids))


def _create_project_with_config(client: TestClient) -> int:
    config = client.post(
        "/api/v1/assignee-rule-configs",
        json={
            "name": f"Default Template Config {uuid4().hex[:8]}",
            "requirement_owner_roles": "product_owner",
            "task_owner_roles": "developer",
            "test_case_tester_roles": "tester",
            "test_run_owner_roles": "tester",
            "bug_owner_roles": "developer",
            "creation_mode": "template",
            "template_source": {"source_type": "system", "source_id": "system-standard"},
        },
    )
    assert config.status_code == 201
    enabled = client.post(f"/api/v1/assignee-rule-configs/{config.json()['id']}/enable")
    assert enabled.status_code == 200, enabled.text
    project = client.post(
        "/api/v1/projects",
        json={"name": f"Default Template Project {uuid4().hex[:8]}", "assignee_rule_config_id": config.json()["id"]},
    )
    assert project.status_code == 200
    return project.json()["id"]


def test_default_template_reconciliation_preserves_state_and_transition_ids(client: TestClient):
    first_list = client.get("/api/v1/workflow-definitions?object_type=requirement&scope_type=system").json()
    definition = next(item for item in first_list if item["is_default_template"] is True)
    first_graph = client.get(f"/api/v1/workflow-definitions/{definition['id']}").json()

    client.get("/api/v1/workflow-definitions?object_type=requirement&scope_type=system")
    second_graph = client.get(f"/api/v1/workflow-definitions/{definition['id']}").json()

    assert [item["id"] for item in second_graph["states"]] == [item["id"] for item in first_graph["states"]]
    assert [item["id"] for item in second_graph["transitions"]] == [
        item["id"] for item in first_graph["transitions"]
    ]
    assert second_graph["definition"]["initial_state_id"] == first_graph["definition"]["initial_state_id"]


def test_default_template_initialization_does_not_overwrite_persisted_state_edits(client: TestClient):
    definitions = client.get(
        "/api/v1/workflow-definitions?object_type=project&scope_type=system"
    ).json()
    definition = next(item for item in definitions if item["is_default_template"] is True)
    graph = client.get(f"/api/v1/workflow-definitions/{definition['id']}").json()
    state_id = graph["states"][0]["id"]
    custom_name = f"项目状态 {uuid4().hex[:8]}"

    db = SessionLocal()
    try:
        state = db.query(WorkflowState).filter(WorkflowState.id == state_id).one()
        original_name = state.status_name
        state.status_name = custom_name
        db.commit()
    finally:
        db.close()

    client.get("/api/v1/workflow-definitions?object_type=project&scope_type=system")
    refreshed = client.get(f"/api/v1/workflow-definitions/{definition['id']}").json()

    assert next(item for item in refreshed["states"] if item["id"] == state_id)["status_name"] == custom_name
    db = SessionLocal()
    try:
        state = db.query(WorkflowState).filter(WorkflowState.id == state_id).one()
        state.status_name = original_name
        db.commit()
    finally:
        db.close()


def _set_requirement_status(requirement_id: int, status: str) -> None:
    db = SessionLocal()
    try:
        requirement = db.query(Requirement).filter(Requirement.id == requirement_id).first()
        assert requirement is not None
        requirement.current_state_id = _state_id_for_status(db, requirement, status)
        db.commit()
    finally:
        db.close()


def _set_requirement_owner_and_status(
    requirement_id: int,
    owner_id: int | None,
    status: str,
    *,
    creator_id: int | None = None,
) -> None:
    db = SessionLocal()
    try:
        requirement = db.query(Requirement).filter(Requirement.id == requirement_id).first()
        assert requirement is not None
        requirement.owner_id = owner_id
        requirement.current_state_id = _state_id_for_status(db, requirement, status)
        if creator_id is not None:
            requirement.creator_id = creator_id
        db.commit()
    finally:
        db.close()


def _set_task_status(task_id: int, status: str) -> None:
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        assert task is not None
        task.current_state_id = _state_id_for_status(db, task, status)
        db.commit()
    finally:
        db.close()


def _set_task_owner_and_status(task_id: int, owner_id: int | None, status: str) -> None:
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        assert task is not None
        task.owner_id = owner_id
        task.current_state_id = _state_id_for_status(db, task, status)
        db.commit()
    finally:
        db.close()


def _set_bug_status(bug_id: int, status: str) -> None:
    db = SessionLocal()
    try:
        bug = db.query(Bug).filter(Bug.id == bug_id).first()
        assert bug is not None
        bug.current_state_id = _state_id_for_status(db, bug, status)
        db.commit()
    finally:
        db.close()


def _set_bug_owner_and_status(bug_id: int, owner_id: int | None, status: str) -> None:
    db = SessionLocal()
    try:
        bug = db.query(Bug).filter(Bug.id == bug_id).first()
        assert bug is not None
        bug.owner_id = owner_id
        bug.current_state_id = _state_id_for_status(db, bug, status)
        db.commit()
    finally:
        db.close()


def _set_iteration_status(iteration_id: int, status: str) -> None:
    db = SessionLocal()
    try:
        iteration = db.query(Iteration).filter(Iteration.id == iteration_id).first()
        assert iteration is not None
        iteration.current_state_id = _state_id_for_status(db, iteration, status)
        db.commit()
    finally:
        db.close()


def _set_project_status(project_id: int, status: str) -> None:
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        assert project is not None
        project.current_state_id = _state_id_for_status(db, project, status)
        db.commit()
    finally:
        db.close()


def test_bug_defaults_to_pending_handling_and_close_blocks_on_direct_task(client: TestClient):
    project_id = _create_project_with_config(client)
    handler_id, handler_token = _create_user("Default Template Developer", "developer")
    _add_project_member(project_id, handler_id, "developer")
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "title": f"Linked task {uuid4().hex[:8]}", "owner_id": handler_id},
    ).json()
    bug = client.post(
        "/api/v1/bugs",
        json={
            "project_id": project_id,
            "task_id": task["id"],
            "title": f"Linked bug {uuid4().hex[:8]}",
            "owner_id": handler_id,
        },
    )

    assert bug.status_code == 200
    assert bug.json()["status_name"] == "待处理"

    _set_bug_status(bug.json()["id"], "verified")
    close = client.post(
        f"/api/v1/workflow-runtime/bug/{bug.json()['id']}/transition",
        json={"action_key": "close", "payload": {"reason": "verified done"}},
        headers={"Authorization": f"Bearer {handler_token}"},
    )

    assert close.status_code == 400
    assert "task" in close.json()["detail"].lower()


def test_task_branch_defaults_follow_confirmation_template(client: TestClient):
    project_id = _create_project_with_config(client)
    handler_id, handler_token = _create_user("Task Branch Developer", "developer")
    _add_project_member(project_id, handler_id, "developer")

    bug_fix_task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "title": f"Bug fix task {uuid4().hex[:8]}",
            "task_type": "bug_fix",
            "owner_id": handler_id,
        },
    )
    requirement_task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "title": f"Requirement task {uuid4().hex[:8]}",
            "task_type": "requirement_implementation",
            "owner_id": handler_id,
        },
    )
    unassigned_task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "title": f"Standalone task {uuid4().hex[:8]}",
            "task_type": "standalone_operation",
        },
    )

    assert bug_fix_task.status_code == 200
    assert bug_fix_task.json()["status_name"]
    assert bug_fix_task.json()["state_category"] == "start"
    assert requirement_task.status_code == 200
    assert requirement_task.json()["status_name"]
    assert requirement_task.json()["state_category"] == "start"
    assert unassigned_task.status_code == 200
    assert unassigned_task.json()["status_name"]
    assert unassigned_task.json()["state_category"] == "start"

    for task_response in (bug_fix_task, requirement_task):
        claimed = client.post(
            f"/api/v1/workflow-runtime/task/{task_response.json()['id']}/transition",
            json={"action_key": "claim"},
            headers={"Authorization": f"Bearer {handler_token}"},
        )
        assert claimed.status_code == 200, claimed.text

    bug_fix_actions = client.get(
        f"/api/v1/workflow-runtime/task/{bug_fix_task.json()['id']}/transitions",
        headers={"Authorization": f"Bearer {handler_token}"},
    )
    requirement_actions = client.get(
        f"/api/v1/workflow-runtime/task/{requirement_task.json()['id']}/transitions",
        headers={"Authorization": f"Bearer {handler_token}"},
    )

    assert bug_fix_actions.status_code == 200
    assert "submit_confirmation" in {item["action_key"] for item in bug_fix_actions.json()}
    assert "complete" not in {item["action_key"] for item in bug_fix_actions.json()}
    assert requirement_actions.status_code == 200
    assert "complete" in {item["action_key"] for item in requirement_actions.json()}


def _action_keys(client: TestClient, object_type: str, object_id: int, token: str) -> set[str]:
    response = client.get(
        f"/api/v1/workflow-runtime/{object_type}/{object_id}/transitions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    return {item["action_key"] for item in response.json()}


def test_default_runtime_actions_match_prd_state_matrix(client: TestClient):
    project_id = _create_project_with_config(client)
    developer_id, developer_token = _create_user("PRD Matrix Developer", "developer")
    owner_id, owner_token = _create_user("PRD Matrix Owner", "project_owner")
    tester_id, tester_token = _create_user("PRD Matrix Tester", "tester")
    _add_project_member(project_id, developer_id, "developer")
    _add_project_member(project_id, owner_id, "project_owner")
    _add_project_member(project_id, tester_id, "tester")

    unassigned_requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"Unassigned requirement {uuid4().hex[:8]}"},
    ).json()
    unassigned_task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "title": f"Unassigned task {uuid4().hex[:8]}"},
    ).json()
    unassigned_bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "title": f"Unassigned bug {uuid4().hex[:8]}"},
    ).json()

    assert "claim" in _action_keys(client, "requirement", unassigned_requirement["id"], developer_token)
    assert "complete" not in _action_keys(client, "requirement", unassigned_requirement["id"], developer_token)
    assert "claim" in _action_keys(client, "task", unassigned_task["id"], developer_token)
    assert "complete" not in _action_keys(client, "task", unassigned_task["id"], developer_token)
    bug_unassigned_actions = _action_keys(client, "bug", unassigned_bug["id"], developer_token)
    assert "claim" in bug_unassigned_actions
    assert "confirm_bug_type" not in bug_unassigned_actions

    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"Owned requirement {uuid4().hex[:8]}", "owner_id": developer_id},
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "title": f"Owned task {uuid4().hex[:8]}",
            "task_type": "bug_fix",
            "owner_id": developer_id,
        },
    ).json()
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "title": f"Owned bug {uuid4().hex[:8]}", "owner_id": developer_id},
    ).json()

    for object_type, item in (("requirement", requirement), ("task", task)):
        claimed = client.post(
            f"/api/v1/workflow-runtime/{object_type}/{item['id']}/transition",
            json={"action_key": "claim"},
            headers={"Authorization": f"Bearer {developer_token}"},
        )
        assert claimed.status_code == 200, claimed.text

    requirement_actions = _action_keys(client, "requirement", requirement["id"], developer_token)
    assert {"complete", "transfer"} <= requirement_actions
    assert "submit_confirmation" not in requirement_actions
    assert "change_handler" in _action_keys(client, "requirement", requirement["id"], owner_token)

    task_actions = _action_keys(client, "task", task["id"], developer_token)
    assert {"submit_confirmation", "transfer"} <= task_actions
    assert "complete" not in task_actions
    assert "change_handler" in _action_keys(client, "task", task["id"], owner_token)

    assert {"confirm_bug_type", "transfer"} <= _action_keys(client, "bug", bug["id"], developer_token)
    assert "change_handler" in _action_keys(client, "bug", bug["id"], owner_token)
    _set_bug_owner_and_status(bug["id"], developer_id, "fixing")
    fixing_actions = _action_keys(client, "bug", bug["id"], developer_token)
    assert {"submit_verification", "reclassify_bug_type", "transfer"} <= fixing_actions
    assert "change_handler" in _action_keys(client, "bug", bug["id"], owner_token)

    _set_bug_owner_and_status(bug["id"], tester_id, "pending_verification")
    verification_actions = _action_keys(client, "bug", bug["id"], tester_token)
    assert {"verification_passed", "verification_failed", "transfer_verification"} <= verification_actions
    assert "assign_verifier" in _action_keys(client, "bug", bug["id"], owner_token)

    _set_bug_owner_and_status(bug["id"], tester_id, "verified")
    verified_actions = _action_keys(client, "bug", bug["id"], tester_token)
    assert {"close", "return_reopen"} <= verified_actions

    _set_bug_owner_and_status(bug["id"], tester_id, "closed")
    assert "activate" in _action_keys(client, "bug", bug["id"], tester_token)

    _set_task_owner_and_status(task["id"], owner_id, "pending_confirmation")
    confirmation_actions = _action_keys(client, "task", task["id"], owner_token)
    assert {"approve_confirmation", "return_rework", "transfer_confirmation"} <= confirmation_actions


def test_default_runtime_actions_enforce_prd_identity_boundaries(client: TestClient):
    project_id = _create_project_with_config(client)
    handler_id, handler_token = _create_user("Identity Handler", "developer")
    creator_id, creator_token = _create_user("Identity Creator", "developer")
    reporter_id, reporter_token = _create_user("Identity Reporter", "tester")
    manager_id, manager_token = _create_user("Identity Manager", "project_owner")
    member_id, member_token = _create_user("Identity Member", "developer")
    for user_id, role in [
        (handler_id, "developer"),
        (creator_id, "developer"),
        (reporter_id, "tester"),
        (manager_id, "project_owner"),
        (member_id, "developer"),
    ]:
        _add_project_member(project_id, user_id, role)

    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "title": f"Identity task {uuid4().hex[:8]}"},
        headers={"Authorization": f"Bearer {creator_token}"},
    ).json()
    creator_actions = _action_keys(client, "task", task["id"], creator_token)
    member_actions = _action_keys(client, "task", task["id"], member_token)
    manager_actions = _action_keys(client, "task", task["id"], manager_token)
    assert {"claim", "cancel", "edit", "add_information"} <= creator_actions
    assert "claim" in member_actions
    assert {"cancel", "edit"}.isdisjoint(member_actions)
    assert {"assign", "cancel"} <= manager_actions

    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "title": f"Identity bug {uuid4().hex[:8]}", "owner_id": handler_id},
        headers={"Authorization": f"Bearer {reporter_token}"},
    ).json()
    handler_actions = _action_keys(client, "bug", bug["id"], handler_token)
    manager_actions = _action_keys(client, "bug", bug["id"], manager_token)
    assert {"confirm_bug_type", "transfer"} <= handler_actions
    assert "void_close" not in handler_actions
    assert {"change_handler", "void_close"} <= manager_actions
    assert "confirm_bug_type" not in manager_actions

    _set_bug_owner_and_status(bug["id"], handler_id, "fixing")
    assert "submit_verification" not in _action_keys(client, "bug", bug["id"], manager_token)

    _set_bug_owner_and_status(bug["id"], handler_id, "verified")
    assert "return_reopen" in _action_keys(client, "bug", bug["id"], reporter_token)
    assert "return_reopen" not in _action_keys(client, "bug", bug["id"], member_token)

    _set_bug_owner_and_status(bug["id"], handler_id, "closed")
    assert "activate" in _action_keys(client, "bug", bug["id"], reporter_token)
    assert "activate" not in _action_keys(client, "bug", bug["id"], member_token)


def test_reactivate_uses_handler_presence_and_completed_requirement_can_reactivate(client: TestClient):
    project_id = _create_project_with_config(client)
    creator_id, creator_token = _create_user("Reactivate Creator", "developer")
    manager_id, manager_token = _create_user("Reactivate Manager", "project_owner")
    restored_id, _ = _create_user("Reactivate Restored Handler", "developer")
    for user_id, role in [
        (creator_id, "developer"),
        (manager_id, "project_owner"),
        (restored_id, "developer"),
    ]:
        _add_project_member(project_id, user_id, role)

    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"Reactivate requirement {uuid4().hex[:8]}"},
        headers={"Authorization": f"Bearer {creator_token}"},
    ).json()
    _set_requirement_owner_and_status(requirement["id"], None, "canceled", creator_id=creator_id)
    unassigned = client.post(
        f"/api/v1/workflow-runtime/requirement/{requirement['id']}/transition",
        json={"action_key": "reactivate", "payload": {"reason": "resume without handler"}},
        headers={"Authorization": f"Bearer {creator_token}"},
    )
    assert unassigned.status_code == 200, unassigned.text
    assert unassigned.json()["status_name"]
    assert unassigned.json()["state_category"] == "start"
    assert unassigned.json()["owner_id"] is None

    _set_requirement_owner_and_status(requirement["id"], None, "canceled")
    assigned = client.post(
        f"/api/v1/workflow-runtime/requirement/{requirement['id']}/transition",
        json={
            "action_key": "reactivate",
            "next_owner_id": restored_id,
            "payload": {"reason": "resume with selected handler"},
            "delegate_reason": "management reactivation",
        },
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert assigned.status_code == 200
    assert assigned.json()["status_name"] == "处理中"
    assert assigned.json()["owner_id"] == restored_id

    _set_requirement_owner_and_status(requirement["id"], restored_id, "completed")
    completed_actions = _action_keys(client, "requirement", requirement["id"], manager_token)
    assert "reactivate" in completed_actions
    reopened = client.post(
        f"/api/v1/workflow-runtime/requirement/{requirement['id']}/transition",
        json={"action_key": "reactivate", "payload": {"reason": "new scope"}, "delegate_reason": "management reactivation"},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert reopened.status_code == 200
    assert reopened.json()["status_name"] == "处理中"
    assert reopened.json()["owner_id"] == restored_id

    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "title": f"Reactivate task {uuid4().hex[:8]}", "owner_id": creator_id},
        headers={"Authorization": f"Bearer {creator_token}"},
    ).json()
    _set_task_owner_and_status(task["id"], creator_id, "canceled")
    task_reopened = client.post(
        f"/api/v1/workflow-runtime/task/{task['id']}/transition",
        json={"action_key": "reactivate", "payload": {"reason": "continue task"}},
        headers={"Authorization": f"Bearer {creator_token}"},
    )
    assert task_reopened.status_code == 200
    assert task_reopened.json()["status_name"] == "处理中"
    assert task_reopened.json()["owner_id"] == creator_id


def test_requirement_and_task_create_reject_legacy_status_even_with_handler(client: TestClient):
    project_id = _create_project_with_config(client)
    handler_id, _ = _create_user("Creation Invariant Handler", "developer")
    _add_project_member(project_id, handler_id, "developer")

    ownerless_requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project_id,
            "title": f"Forged active requirement {uuid4().hex[:8]}",
            "status": "in_processing",
        },
    )
    assigned_requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project_id,
            "title": f"Forged unassigned requirement {uuid4().hex[:8]}",
            "owner_id": handler_id,
            "status": "pending_assignment",
        },
    )
    ownerless_task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "title": f"Forged active task {uuid4().hex[:8]}",
            "status": "in_processing",
        },
    )
    assigned_task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "title": f"Forged unassigned task {uuid4().hex[:8]}",
            "owner_id": handler_id,
            "status": "pending_assignment",
        },
    )

    assert ownerless_requirement.status_code == 422
    assert assigned_requirement.status_code == 422
    assert ownerless_task.status_code == 422
    assert assigned_task.status_code == 422


def test_requirement_complete_and_cancel_block_on_direct_relations(client: TestClient):
    project_id = _create_project_with_config(client)
    handler_id, handler_token = _create_user("Requirement Handler", "developer")
    _add_project_member(project_id, handler_id, "developer")
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"Requirement {uuid4().hex[:8]}", "owner_id": handler_id},
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "requirement_id": requirement["id"],
            "title": f"Requirement task {uuid4().hex[:8]}",
            "owner_id": handler_id,
        },
    ).json()
    bug = client.post(
        "/api/v1/bugs",
        json={
            "project_id": project_id,
            "requirement_id": requirement["id"],
            "title": f"Requirement bug {uuid4().hex[:8]}",
            "owner_id": handler_id,
        },
    ).json()
    _set_requirement_status(requirement["id"], "in_processing")
    _set_task_status(task["id"], "completed")
    _set_bug_status(bug["id"], "pending_verification")

    complete = client.post(
        f"/api/v1/workflow-runtime/requirement/{requirement['id']}/transition",
        json={"action_key": "complete", "payload": {}},
        headers={"Authorization": f"Bearer {handler_token}"},
    )

    assert complete.status_code == 400
    assert "bug" in complete.json()["detail"].lower()

    _set_bug_status(bug["id"], "closed")
    _set_task_status(task["id"], "in_processing")
    cancel = client.post(
        f"/api/v1/workflow-runtime/requirement/{requirement['id']}/transition",
        json={"action_key": "cancel", "payload": {"reason": "scope removed"}},
        headers={"Authorization": f"Bearer {handler_token}"},
    )

    assert cancel.status_code == 400
    assert "task" in cancel.json()["detail"].lower()


def test_iteration_complete_and_cancel_block_on_direct_items(client: TestClient):
    project_id = _create_project_with_config(client)
    handler_id, handler_token = _create_user("Iteration Handler", "project_owner")
    _add_project_member(project_id, handler_id, "project_owner")
    iteration = client.post(
        "/api/v1/iterations",
        json={"project_ids": [project_id], "name": f"Iteration {uuid4().hex[:8]}"},
    ).json()
    client.post(
        "/api/v1/requirements",
        json={
            "project_id": project_id,
            "iteration_id": iteration["id"],
            "title": f"Iteration requirement {uuid4().hex[:8]}",
            "owner_id": handler_id,
        },
    )
    client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "iteration_id": iteration["id"],
            "title": f"Iteration task {uuid4().hex[:8]}",
            "owner_id": handler_id,
        },
    )
    client.post(
        "/api/v1/bugs",
        json={
            "project_id": project_id,
            "iteration_id": iteration["id"],
            "title": f"Iteration bug {uuid4().hex[:8]}",
            "owner_id": handler_id,
        },
    )
    _set_iteration_status(iteration["id"], "active")

    complete = client.post(
        f"/api/v1/workflow-runtime/iteration/{iteration['id']}/transition",
        json={"action_key": "complete", "payload": {}},
        headers={"Authorization": f"Bearer {handler_token}"},
    )
    cancel = client.post(
        f"/api/v1/workflow-runtime/iteration/{iteration['id']}/transition",
        json={"action_key": "cancel", "payload": {"reason": "stop iteration"}},
        headers={"Authorization": f"Bearer {handler_token}"},
    )

    assert complete.status_code == 400
    assert "requirement" in complete.json()["detail"].lower() or "bug" in complete.json()["detail"].lower()
    assert cancel.status_code == 400
    assert "task" in cancel.json()["detail"].lower() or "bug" in cancel.json()["detail"].lower()


def test_project_close_blocks_on_direct_scoped_objects(client: TestClient):
    project_id = _create_project_with_config(client)
    handler_id, handler_token = _create_user("Project Owner", "project_owner")
    _add_project_member(project_id, handler_id, "project_owner")
    iteration = client.post(
        "/api/v1/iterations",
        json={"project_ids": [project_id], "name": f"Project iteration {uuid4().hex[:8]}"},
    ).json()
    client.post(
        "/api/v1/bugs",
        json={
            "project_id": project_id,
            "iteration_id": iteration["id"],
            "title": f"Project bug {uuid4().hex[:8]}",
            "owner_id": handler_id,
        },
    )
    _set_project_status(project_id, "active")

    close = client.post(
        f"/api/v1/workflow-runtime/project/{project_id}/transition",
        json={"action_key": "close", "payload": {"reason": "release done"}},
        headers={"Authorization": f"Bearer {handler_token}"},
    )

    assert close.status_code == 400
    assert "bug" in close.json()["detail"].lower() or "iteration" in close.json()["detail"].lower()
