from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.session import SessionLocal
from app.models.bug import Bug
from app.models.iteration import Iteration
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.requirement import Requirement
from app.models.role import RoleCapability
from app.models.task import Task
from app.models.user import User
from app.models.workflow_definition import WorkflowState, WorkflowTransition
from app.services import default_workflow_template_service
from app.services.default_workflow_template_service import graph_for_object_type
from app.views.workflow_definition_view import WorkflowTemplateState, WorkflowTemplateTransition


@pytest.fixture(autouse=True)
def _real_iteration_defaults(client: TestClient):
    client.enable_real_iteration_defaults()


def test_template_build_contract_uses_request_local_refs_not_status_columns():
    assert set(WorkflowTemplateState.model_fields) >= {"ref", "status_name", "terminal_kind"}
    assert "status_key" not in WorkflowTemplateState.model_fields
    assert set(WorkflowTemplateTransition.model_fields) >= {"from_ref", "to_ref"}
    assert "from_status" not in WorkflowTemplateTransition.model_fields
    assert "to_status" not in WorkflowTemplateTransition.model_fields


def test_project_start_is_a_primary_list_action():
    graph = graph_for_object_type("project")
    start = next(item for item in graph.transitions if item.action_key == "start")

    assert start.ui_config["list_display"] == "primary"


def test_work_item_add_information_actions_are_named_comment():
    for object_type in ("requirement", "task", "bug"):
        graph = graph_for_object_type(object_type)
        comment_actions = [
            transition
            for transition in graph.transitions
            if transition.action_key == "add_information"
        ]

        assert comment_actions
        assert {transition.action_name for transition in comment_actions} == {"评论"}


def test_template_initialization_does_not_reconcile_existing_workflows_by_default(monkeypatch):
    calls = []

    monkeypatch.setattr(
        default_workflow_template_service,
        "reconcile_review_subgraph",
        lambda *_args: calls.append("review"),
    )
    monkeypatch.setattr(
        default_workflow_template_service,
        "reconcile_work_item_state_matrix",
        lambda *_args: calls.append("state_matrix"),
    )
    monkeypatch.setattr(
        default_workflow_template_service,
        "reconcile_managed_bug_action_matrices",
        lambda *_args: calls.append("bug_actions"),
    )
    monkeypatch.setattr(
        default_workflow_template_service,
        "reconcile_managed_task_terminal_gates",
        lambda *_args: calls.append("task_gates"),
    )

    with SessionLocal() as db:
        default_workflow_template_service.ensure_default_workflow_templates(db)

    assert calls == []


def _create_user(full_name: str, role_key: str) -> tuple[int, str]:
    db = SessionLocal()
    try:
        user = User(
            username=f"default_template_{uuid4().hex[:8]}",
            full_name=full_name,
            password_hash=get_password_hash("User123456"),
            is_active=True,
            is_system_admin=role_key == "system_admin",
        )
        db.add(user)
        db.flush()
        db.commit()
        return user.id, create_access_token(user.username)
    finally:
        db.close()


def _add_project_member(project_id: int, user_id: int, project_role: str) -> None:
    db = SessionLocal()
    try:
        capability = {"product_owner": "product_manager", "project_member": "viewer"}.get(project_role, project_role)
        role_id = db.query(RoleCapability.role_id).filter(RoleCapability.capability == capability).scalar()
        assert role_id is not None, f"Missing role capability: {capability}"
        db.add(
            ProjectMember(
                project_id=project_id,
                user_id=user_id,
                role_id=role_id,
                is_workbench_participant=True,
            )
        )
        db.commit()
    finally:
        db.close()


def _state_id_for_status(db, item, status: str) -> int:
    state_role_by_status = {
        "pending_assignment": "unassigned",
        "pending_handling": "unassigned",
        "in_processing": "active_work",
        "fixing": "active_work",
    }
    action_by_status = {
        "pending_confirmation": "submit_confirmation",
        "completed": "complete",
        "canceled": "cancel",
        "pending_verification": "submit_verification",
        "verified": "verification_passed",
        "closed": "close",
        "active": "start",
        "paused": "suspend",
    }
    if status in state_role_by_status:
        state_ids = {
            value
            for value, in db.query(WorkflowState.id).filter(
                WorkflowState.definition_id == item.workflow_definition_id,
                WorkflowState.state_role == state_role_by_status[status],
            ).all()
        }
    elif status == "planning":
        state_ids = {
            value
            for value, in db.query(WorkflowState.id).filter(
                WorkflowState.definition_id == item.workflow_definition_id,
                WorkflowState.category == "start",
            ).all()
        }
    elif status in {"completed", "canceled"}:
        terminal_kind = "completed" if status == "completed" else "terminated"
        state_ids = {
            value
            for value, in db.query(WorkflowState.id).filter(
                WorkflowState.definition_id == item.workflow_definition_id,
                WorkflowState.category == "terminal",
                WorkflowState.terminal_kind == terminal_kind,
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


def _set_requirement_to_terminal_gate_source(requirement_id: int) -> str:
    db = SessionLocal()
    try:
        requirement = db.query(Requirement).filter(Requirement.id == requirement_id).one()
        states = {
            state.id: state
            for state in db.query(WorkflowState)
            .filter(WorkflowState.definition_id == requirement.workflow_definition_id)
            .all()
        }
        transitions = (
            db.query(WorkflowTransition)
            .filter(
                WorkflowTransition.definition_id == requirement.workflow_definition_id,
                WorkflowTransition.enabled.is_(True),
            )
            .order_by(WorkflowTransition.sort_order.asc(), WorkflowTransition.id.asc())
            .all()
        )
        transition = next(
            item
            for item in transitions
            if states[item.to_state_id].category == "terminal"
            and any(
                validator.get("type") == "requirement_terminal_gate"
                for validator in (
                    item.validator_config
                    if isinstance(item.validator_config, list)
                    else [item.validator_config]
                )
                if validator
            )
        )
        requirement.current_state_id = transition.from_state_id
        db.commit()
        return transition.action_key
    finally:
        db.close()


def _create_project_with_config(client: TestClient) -> int:
    with SessionLocal() as db:
        role_ids = {
            capability: db.query(RoleCapability.role_id).filter(RoleCapability.capability == capability).scalar()
            for capability in ("product_manager", "developer", "tester")
        }
    assert all(role_ids.values())
    config = client.post(
        "/api/v1/assignee-rule-configs",
        json={
            "name": f"Default Template Config {uuid4().hex[:8]}",
            "requirement_owner_role_ids": [role_ids["product_manager"]],
            "task_owner_role_ids": [role_ids["developer"]],
            "test_case_tester_role_ids": [role_ids["tester"]],
            "test_run_owner_role_ids": [role_ids["tester"]],
            "bug_owner_role_ids": [role_ids["developer"]],
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
    assert project.status_code == 200, project.text
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


def test_bug_system_template_initialization_preserves_persisted_unassigned_name(client: TestClient):
    definitions = client.get(
        "/api/v1/workflow-definitions?object_type=bug&scope_type=system"
    ).json()
    definition = next(item for item in definitions if item["is_default_template"] is True)
    graph = client.get(f"/api/v1/workflow-definitions/{definition['id']}").json()
    state_id = next(item["id"] for item in graph["states"] if item["state_role"] == "unassigned")
    custom_name = f"待处理 {uuid4().hex[:8]}"

    db = SessionLocal()
    try:
        state = db.query(WorkflowState).filter(WorkflowState.id == state_id).one()
        original_name = state.status_name
        state.status_name = custom_name
        db.commit()

        client.get("/api/v1/workflow-definitions?object_type=bug&scope_type=system")
        refreshed = client.get(f"/api/v1/workflow-definitions/{definition['id']}").json()

        assert next(item for item in refreshed["states"] if item["id"] == state_id)["status_name"] == custom_name
    finally:
        state = db.query(WorkflowState).filter(WorkflowState.id == state_id).one()
        state.status_name = original_name
        db.commit()
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


def test_bug_defaults_to_active_work_and_close_blocks_on_direct_task(client: TestClient):
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
    assert _state_role(bug.json()) == "active_work"

    _set_bug_status(bug.json()["id"], "verified")
    close = client.post(
        f"/api/v1/workflow-runtime/bug/{bug.json()['id']}/transition",
        json={"action_key": "close", "payload": {"reason": "verified done"}},
        headers={"Authorization": f"Bearer {handler_token}"},
    )

    assert close.status_code == 400
    assert close.json()["detail"]["code"] == "BUG_LINKED_TASKS_UNFINISHED"


def test_task_branch_defaults_follow_confirmation_template(client: TestClient):
    project_id = _create_project_with_config(client)
    handler_id, handler_token = _create_user("Task Branch Developer", "developer")
    _add_project_member(project_id, handler_id, "developer")
    iteration = client.post(
        "/api/v1/iterations",
        json={"project_ids": [project_id], "name": f"Task branch iteration {uuid4().hex[:8]}"},
    )
    assert iteration.status_code == 200, iteration.text
    started = client.post(
        f"/api/v1/workflow-runtime/iteration/{iteration.json()['id']}/transition",
        json={"action_key": "start"},
    )
    assert started.status_code == 200, started.text

    bug_fix_task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "iteration_id": iteration.json()["id"],
            "title": f"Bug fix task {uuid4().hex[:8]}",
            "task_type": "bug_fix",
            "owner_id": handler_id,
        },
    )
    requirement_task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "iteration_id": iteration.json()["id"],
            "title": f"Requirement task {uuid4().hex[:8]}",
            "task_type": "requirement_implementation",
            "owner_id": handler_id,
        },
    )
    unassigned_task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "iteration_id": iteration.json()["id"],
            "title": f"Standalone task {uuid4().hex[:8]}",
            "task_type": "standalone_operation",
        },
    )

    assert bug_fix_task.status_code == 200
    assert _state_role(bug_fix_task.json()) == "active_work"
    assert requirement_task.status_code == 200
    assert _state_role(requirement_task.json()) == "active_work"
    assert unassigned_task.status_code == 200
    assert _state_role(unassigned_task.json()) == "unassigned"

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


def _state_role(item: dict) -> str | None:
    with SessionLocal() as db:
        return db.query(WorkflowState.state_role).filter(
            WorkflowState.id == item["current_state_id"]
        ).scalar()


def _create_active_iteration(client: TestClient, project_id: int) -> int:
    iteration = client.post(
        "/api/v1/iterations",
        json={"project_ids": [project_id], "name": f"Active Bug Matrix {uuid4().hex[:8]}"},
    )
    assert iteration.status_code == 200, iteration.text
    started = client.post(
        f"/api/v1/workflow-runtime/iteration/{iteration.json()['id']}/transition",
        json={"action_key": "start"},
    )
    assert started.status_code == 200, started.text
    return iteration.json()["id"]


def _create_planned_iteration(client: TestClient, project_id: int) -> int:
    iteration = client.post(
        "/api/v1/iterations",
        json={"project_ids": [project_id], "name": f"Planned Bug Matrix {uuid4().hex[:8]}"},
    )
    assert iteration.status_code == 200, iteration.text
    return iteration.json()["id"]


def test_default_runtime_actions_match_prd_state_matrix(client: TestClient):
    project_id = _create_project_with_config(client)
    developer_id, developer_token = _create_user("PRD Matrix Developer", "developer")
    owner_id, owner_token = _create_user("PRD Matrix Owner", "project_owner")
    _add_project_member(project_id, developer_id, "developer")
    _add_project_member(project_id, owner_id, "project_owner")

    graph = graph_for_object_type("bug")
    states_by_role = {state.state_role: state for state in graph.states}
    actions_by_role = {
        role: {transition.action_key for transition in graph.transitions if transition.from_ref == state.ref}
        for role, state in states_by_role.items()
    }
    assert {"claim", "assign", "edit"} <= actions_by_role["unassigned"]
    assert {"transfer", "change_handler"}.isdisjoint(actions_by_role["unassigned"])
    assert {"transfer", "change_handler", "edit"} <= actions_by_role["waiting_iteration"]
    assert {"transfer", "change_handler"} <= actions_by_role["active_work"]
    assert "edit" not in actions_by_role["active_work"]
    assert {
        transition.from_ref
        for transition in graph.transitions
        if transition.action_key == "edit"
    } == {states_by_role["unassigned"].ref, states_by_role["waiting_iteration"].ref}

    unassigned_response = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "title": f"Unassigned bug {uuid4().hex[:8]}"},
        headers={"Authorization": f"Bearer {developer_token}"},
    )
    assert unassigned_response.status_code == 200, unassigned_response.text
    unassigned_bug = unassigned_response.json()
    assert _state_role(unassigned_bug) == "unassigned"
    assert {"claim", "edit"} <= _action_keys(client, "bug", unassigned_bug["id"], developer_token)
    assert "assign" in _action_keys(client, "bug", unassigned_bug["id"], owner_token)

    waiting_response = client.post(
        "/api/v1/bugs",
        json={
            "project_id": project_id,
            "iteration_id": _create_planned_iteration(client, project_id),
            "title": f"Waiting bug {uuid4().hex[:8]}",
            "owner_id": developer_id,
        },
        headers={"Authorization": f"Bearer {developer_token}"},
    )
    assert waiting_response.status_code == 200, waiting_response.text
    waiting_bug = waiting_response.json()
    assert _state_role(waiting_bug) == "waiting_iteration"
    assert {"transfer", "edit"} <= _action_keys(client, "bug", waiting_bug["id"], developer_token)
    assert "change_handler" in _action_keys(client, "bug", waiting_bug["id"], owner_token)

    active_response = client.post(
        "/api/v1/bugs",
        json={
            "project_id": project_id,
            "iteration_id": _create_active_iteration(client, project_id),
            "title": f"Active bug {uuid4().hex[:8]}",
            "owner_id": developer_id,
        },
        headers={"Authorization": f"Bearer {developer_token}"},
    )
    assert active_response.status_code == 200, active_response.text
    active_bug = active_response.json()
    assert _state_role(active_bug) == "active_work"
    active_actions = _action_keys(client, "bug", active_bug["id"], developer_token)
    assert "transfer" in active_actions
    assert "edit" not in active_actions
    assert "change_handler" in _action_keys(client, "bug", active_bug["id"], owner_token)


def test_default_runtime_actions_enforce_prd_identity_boundaries(client: TestClient):
    project_id = _create_project_with_config(client)
    handler_id, handler_token = _create_user("Identity Handler", "developer")
    creator_id, creator_token = _create_user("Identity Creator", "developer")
    manager_id, manager_token = _create_user("Identity Manager", "project_owner")
    member_id, member_token = _create_user("Identity Member", "developer")
    for user_id, role in [
        (handler_id, "developer"),
        (creator_id, "developer"),
        (manager_id, "project_owner"),
        (member_id, "developer"),
    ]:
        _add_project_member(project_id, user_id, role)

    unassigned = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "title": f"Identity unassigned bug {uuid4().hex[:8]}"},
        headers={"Authorization": f"Bearer {creator_token}"},
    )
    assert unassigned.status_code == 200, unassigned.text
    unassigned_bug = unassigned.json()
    assert "edit" in _action_keys(client, "bug", unassigned_bug["id"], creator_token)
    assert "edit" not in _action_keys(client, "bug", unassigned_bug["id"], member_token)
    assert "edit" not in _action_keys(client, "bug", unassigned_bug["id"], manager_token)

    waiting = client.post(
        "/api/v1/bugs",
        json={
            "project_id": project_id,
            "iteration_id": _create_planned_iteration(client, project_id),
            "title": f"Identity waiting bug {uuid4().hex[:8]}",
            "owner_id": handler_id,
        },
        headers={"Authorization": f"Bearer {creator_token}"},
    )
    assert waiting.status_code == 200, waiting.text
    waiting_bug = waiting.json()
    assert _state_role(waiting_bug) == "waiting_iteration"
    assert "edit" in _action_keys(client, "bug", waiting_bug["id"], creator_token)
    assert "transfer" in _action_keys(client, "bug", waiting_bug["id"], handler_token)
    assert "change_handler" in _action_keys(client, "bug", waiting_bug["id"], manager_token)
    assert {"edit", "transfer", "change_handler"}.isdisjoint(
        _action_keys(client, "bug", waiting_bug["id"], member_token)
    )


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

    _set_requirement_owner_and_status(requirement["id"], None, "canceled")
    creator_assigned = client.post(
        f"/api/v1/workflow-runtime/requirement/{requirement['id']}/transition",
        json={
            "action_key": "reactivate",
            "next_owner_id": restored_id,
            "payload": {"reason": "creator selects an eligible handler"},
        },
        headers={"Authorization": f"Bearer {creator_token}"},
    )
    assert creator_assigned.status_code == 200, creator_assigned.text
    assert creator_assigned.json()["owner_id"] == restored_id

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
    _add_project_member(project_id, handler_id, "project_owner")
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"Requirement {uuid4().hex[:8]}", "owner_id": handler_id},
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "iteration_id": requirement["iteration_id"],
            "requirement_id": requirement["id"],
            "title": f"Requirement task {uuid4().hex[:8]}",
            "owner_id": handler_id,
        },
    ).json()
    bug = client.post(
        "/api/v1/bugs",
        json={
            "project_id": project_id,
            "iteration_id": requirement["iteration_id"],
            "requirement_id": requirement["id"],
            "title": f"Requirement bug {uuid4().hex[:8]}",
            "owner_id": handler_id,
        },
        headers={"X-Test-Require-Explicit-Iteration": "1"},
    ).json()
    started = client.post(
        f"/api/v1/workflow-runtime/iteration/{requirement['iteration_id']}/transition",
        json={"action_key": "start"},
        headers={"Authorization": f"Bearer {handler_token}"},
    )
    assert started.status_code == 200, started.text
    terminal_action_key = _set_requirement_to_terminal_gate_source(requirement["id"])
    _set_task_status(task["id"], "completed")
    _set_bug_status(bug["id"], "pending_verification")

    complete = client.post(
        f"/api/v1/workflow-runtime/requirement/{requirement['id']}/transition",
        json={"action_key": terminal_action_key, "payload": {}},
        headers={"Authorization": f"Bearer {handler_token}"},
    )

    assert complete.status_code == 400
    assert complete.json()["detail"]["code"] == "REQUIREMENT_HAS_UNCLOSED_BUGS"

    _set_bug_status(bug["id"], "closed")
    _set_task_status(task["id"], "in_processing")
    cancel = client.post(
        f"/api/v1/workflow-runtime/requirement/{requirement['id']}/transition",
        json={"action_key": terminal_action_key, "payload": {"reason": "scope removed"}},
        headers={"Authorization": f"Bearer {handler_token}"},
    )

    assert cancel.status_code == 400
    assert cancel.json()["detail"]["code"] == "REQUIREMENT_HAS_UNFINISHED_TASKS"


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
    assert complete.json()["detail"]["code"] == "ITERATION_HAS_OPEN_ITEMS"
    assert complete.json()["detail"]["counts"]["requirement"] == 1
    assert complete.json()["detail"]["counts"]["bug"] == 1
    assert cancel.status_code == 400
    assert cancel.json()["detail"]["code"] == "ITERATION_HAS_OPEN_ITEMS"
    assert cancel.json()["detail"]["counts"]["task"] == 1


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
        json={"action_key": "close", "payload": {"reason": "release done", "effective_time": "2026-07-20"}},
        headers={"Authorization": f"Bearer {handler_token}"},
    )

    assert close.status_code == 400
    assert close.json()["detail"]["code"] == "PROJECT_HAS_UNFINISHED_ITEMS"
