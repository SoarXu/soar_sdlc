from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.session import SessionLocal
from app.models.project_member import ProjectMember
from app.models.requirement import Requirement
from app.models.role import Role, UserRole
from app.models.user import User
from app.models.workflow_definition import WorkflowTransition


def _create_user(full_name: str, role_key: str | None = None) -> tuple[int, str]:
    db = SessionLocal()
    try:
        user = User(
            username=f"runtime_{uuid4().hex[:8]}",
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


def _create_project_with_bug_workflow(client: TestClient) -> tuple[int, int]:
    config = client.post(
        "/api/v1/assignee-rule-configs",
        json={
            "name": f"Runtime Config {uuid4().hex[:8]}",
            "requirement_owner_roles": "",
            "task_owner_roles": "",
            "test_case_tester_roles": "tester",
            "test_run_owner_roles": "tester",
            "bug_owner_roles": "",
        },
    )
    assert config.status_code == 201
    project = client.post(
        "/api/v1/projects",
        json={"name": f"Runtime Project {uuid4().hex[:8]}", "assignee_rule_config_id": config.json()["id"]},
    )
    assert project.status_code == 200
    definition = client.post(
        "/api/v1/workflow-definitions",
        json={
            "name": f"Runtime Bug Workflow {uuid4().hex[:8]}",
            "object_type": "bug",
            "scope_type": "assignee_rule_config",
            "scope_id": config.json()["id"],
        },
    )
    assert definition.status_code == 201
    graph = client.put(
        f"/api/v1/workflow-definitions/{definition.json()['id']}/graph",
        json={
            "states": [
                {"status_key": "open", "status_name": "Open", "category": "start", "x": 100, "y": 100},
                {"status_key": "fixing", "status_name": "Fixing", "category": "normal", "x": 300, "y": 100},
                {"status_key": "closed", "status_name": "Closed", "category": "terminal", "x": 500, "y": 100},
            ],
            "transitions": [
                {
                    "action_key": "start_fixing",
                    "action_name": "确认",
                    "from_status": "open",
                    "to_status": "fixing",
                    "handler_rule": {
                        "target_type": "project_role",
                        "target_roles": "developer",
                        "fallback_type": "keep_current",
                    },
                    "ui_config": {
                        "button_type": "success",
                        "list_display": "primary",
                        "list_priority": 10,
                    },
                },
                {
                    "action_key": "close",
                    "action_name": "关闭",
                    "from_status": "open",
                    "to_status": "closed",
                    "handler_rule": {"target_type": "keep_current", "fallback_type": "keep_current"},
                    "ui_config": {
                        "button_type": "danger",
                        "list_display": "more",
                        "list_priority": 100,
                        "confirm_required": True,
                    },
                    "form_config": {
                        "title": "关闭 Bug",
                        "fields": [{"field": "reason", "label": "关闭原因", "type": "text", "required": True}],
                    },
                },
            ],
        },
    )
    assert graph.status_code == 200
    return config.json()["id"], project.json()["id"]


def _create_project_with_requirement_workflow(client: TestClient) -> tuple[int, int]:
    config = client.post(
        "/api/v1/assignee-rule-configs",
        json={
            "name": f"Runtime Requirement Config {uuid4().hex[:8]}",
            "requirement_owner_roles": "",
            "task_owner_roles": "",
            "test_case_tester_roles": "tester",
            "test_run_owner_roles": "tester",
            "bug_owner_roles": "",
        },
    )
    assert config.status_code == 201
    project = client.post(
        "/api/v1/projects",
        json={"name": f"Runtime Requirement Project {uuid4().hex[:8]}", "assignee_rule_config_id": config.json()["id"]},
    )
    assert project.status_code == 200
    definition = client.post(
        "/api/v1/workflow-definitions",
        json={
            "name": f"Runtime Requirement Workflow {uuid4().hex[:8]}",
            "object_type": "requirement",
            "scope_type": "assignee_rule_config",
            "scope_id": config.json()["id"],
        },
    )
    assert definition.status_code == 201
    graph = client.put(
        f"/api/v1/workflow-definitions/{definition.json()['id']}/graph",
        json={
            "states": [
                {"status_key": "active", "status_name": "Active", "category": "normal", "x": 100, "y": 100},
                {"status_key": "draft", "status_name": "Draft", "category": "start", "x": 300, "y": 100},
            ],
            "transitions": [
                {
                    "action_key": "defer",
                    "action_name": "延期",
                    "from_status": "active",
                    "to_status": "draft",
                    "handler_rule": {"target_type": "keep_current", "fallback_type": "keep_current"},
                    "form_config": {
                        "fields": [
                            {"field": "target_iteration_id", "label": "目标迭代", "type": "number", "required": False},
                            {"field": "remark", "label": "备注", "type": "textarea", "required": False},
                        ]
                    },
                }
            ],
        },
    )
    assert graph.status_code == 200
    return config.json()["id"], project.json()["id"]


def test_runtime_lists_configured_transitions_and_batch(client: TestClient):
    _, project_id = _create_project_with_bug_workflow(client)
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "title": f"Runtime Bug {uuid4().hex[:8]}", "owner_id": None},
    ).json()

    listed = client.get(f"/api/v1/workflow-runtime/bug/{bug['id']}/transitions")
    batch = client.post(
        "/api/v1/workflow-runtime/transitions/batch",
        json={"items": [{"object_type": "bug", "id": bug["id"]}]},
    )

    assert listed.status_code == 200
    assert [item["action_key"] for item in listed.json()] == ["start_fixing", "close"]
    assert listed.json()[0]["list_display"] == "primary"
    assert listed.json()[1]["form_config"]["title"] == "关闭 Bug"
    assert batch.status_code == 200
    assert batch.json()["items"][0]["transitions"][0]["action_name"] == "确认"


def test_runtime_exposes_manual_owner_flag_from_handler_rule(client: TestClient):
    _, project_id = _create_project_with_bug_workflow(client)
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "title": f"Manual Owner Bug {uuid4().hex[:8]}", "owner_id": None},
    ).json()
    db = SessionLocal()
    try:
        from app.models.workflow_definition import WorkflowTransition

        transition = (
            db.query(WorkflowTransition)
            .filter(WorkflowTransition.action_key == "start_fixing")
            .order_by(WorkflowTransition.id.desc())
            .first()
        )
        transition.handler_rule = {**(transition.handler_rule or {}), "allow_manual_owner": True}
        db.commit()
    finally:
        db.close()

    listed = client.get(f"/api/v1/workflow-runtime/bug/{bug['id']}/transitions")

    assert listed.status_code == 200
    assert listed.json()[0]["form_config"]["allow_manual_owner"] is True


def test_runtime_executes_transition_and_assigns_next_handler(client: TestClient):
    _, project_id = _create_project_with_bug_workflow(client)
    developer_id, developer_token = _create_user("Runtime Developer", "developer")
    _add_project_member(project_id, developer_id, "developer")
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "title": f"Execute Bug {uuid4().hex[:8]}", "owner_id": developer_id},
    ).json()

    executed = client.post(
        f"/api/v1/workflow-runtime/bug/{bug['id']}/transition",
        json={"action_key": "start_fixing", "payload": {"remark": "take it"}},
        headers={"Authorization": f"Bearer {developer_token}"},
    )

    assert executed.status_code == 200
    assert executed.json()["status"] == "fixing"
    assert executed.json()["owner_id"] == developer_id
    history = client.get(f"/api/v1/bugs/{bug['id']}/status-operations").json()
    assert history[-1]["action"] == "start_fixing"
    assert history[-1]["actor_name"] == "Runtime Developer"


def test_runtime_manager_delegate_requires_reason_and_records_snapshot(client: TestClient):
    _, project_id = _create_project_with_bug_workflow(client)
    developer_id, _ = _create_user("Original Developer", "developer")
    manager_id, manager_token = _create_user("Runtime Manager", "project_owner")
    _add_project_member(project_id, developer_id, "developer")
    _add_project_member(project_id, manager_id, "project_owner")
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "title": f"Delegate Bug {uuid4().hex[:8]}", "owner_id": developer_id},
    ).json()

    missing_reason = client.post(
        f"/api/v1/workflow-runtime/bug/{bug['id']}/transition",
        json={"action_key": "start_fixing"},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    delegated = client.post(
        f"/api/v1/workflow-runtime/bug/{bug['id']}/transition",
        json={"action_key": "start_fixing", "delegate_reason": "urgent release"},
        headers={"Authorization": f"Bearer {manager_token}"},
    )

    assert missing_reason.status_code == 422
    assert delegated.status_code == 200
    history = client.get(f"/api/v1/bugs/{bug['id']}/status-operations").json()
    assert history[-1]["is_delegated"] is True
    assert history[-1]["actor_name"] == "Runtime Manager"
    assert history[-1]["delegated_owner_name"] == "Original Developer"
    assert history[-1]["delegate_reason"] == "urgent release"


def test_runtime_hides_transitions_from_non_handler_and_allows_manager_delegate(client: TestClient):
    _, project_id = _create_project_with_bug_workflow(client)
    owner_id, _ = _create_user("Runtime Owner", "developer")
    other_id, other_token = _create_user("Runtime Other", "developer")
    manager_id, manager_token = _create_user("Runtime Lead", "project_owner")
    _add_project_member(project_id, owner_id, "developer")
    _add_project_member(project_id, other_id, "developer")
    _add_project_member(project_id, manager_id, "project_owner")
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "title": f"Visibility Bug {uuid4().hex[:8]}", "owner_id": owner_id},
    ).json()

    other_visible = client.get(
        f"/api/v1/workflow-runtime/bug/{bug['id']}/transitions",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    manager_visible = client.get(
        f"/api/v1/workflow-runtime/bug/{bug['id']}/transitions",
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    other_execute = client.post(
        f"/api/v1/workflow-runtime/bug/{bug['id']}/transition",
        json={"action_key": "start_fixing"},
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert other_visible.status_code == 200
    assert other_visible.json() == []
    assert manager_visible.status_code == 200
    assert [item["action_key"] for item in manager_visible.json()] == ["start_fixing", "close"]
    assert other_execute.status_code == 403


def test_runtime_manual_owner_respects_configured_roles(client: TestClient):
    _, project_id = _create_project_with_bug_workflow(client)
    owner_id, owner_token = _create_user("Runtime Manual Owner", "developer")
    developer_id, _ = _create_user("Runtime Next Developer", "developer")
    tester_id, _ = _create_user("Runtime Tester", "tester")
    _add_project_member(project_id, owner_id, "developer")
    _add_project_member(project_id, developer_id, "developer")
    _add_project_member(project_id, tester_id, "tester")
    db = SessionLocal()
    try:
        transition = (
            db.query(WorkflowTransition)
            .filter(WorkflowTransition.action_key == "start_fixing")
            .order_by(WorkflowTransition.id.desc())
            .first()
        )
        transition.handler_rule = {
            **(transition.handler_rule or {}),
            "allow_manual_owner": True,
            "manual_owner_roles": "developer",
        }
        db.commit()
    finally:
        db.close()
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "title": f"Manual Role Bug {uuid4().hex[:8]}", "owner_id": owner_id},
    ).json()

    rejected = client.post(
        f"/api/v1/workflow-runtime/bug/{bug['id']}/transition",
        json={"action_key": "start_fixing", "next_owner_id": tester_id},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    accepted = client.post(
        f"/api/v1/workflow-runtime/bug/{bug['id']}/transition",
        json={"action_key": "start_fixing", "next_owner_id": developer_id},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert rejected.status_code == 400
    assert accepted.status_code == 200
    assert accepted.json()["owner_id"] == developer_id


def test_runtime_requirement_defer_moves_tasks_and_test_cases(client: TestClient):
    _, project_id = _create_project_with_requirement_workflow(client)
    owner_id, owner_token = _create_user("Runtime Requirement Owner", "developer")
    _add_project_member(project_id, owner_id, "developer")
    current_iteration = client.post(
        "/api/v1/iterations",
        json={"name": f"Runtime Current Iteration {uuid4().hex[:8]}", "project_ids": [project_id]},
    ).json()
    target_iteration = client.post(
        "/api/v1/iterations",
        json={"name": f"Runtime Target Iteration {uuid4().hex[:8]}", "project_ids": [project_id]},
    ).json()
    requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project_id,
            "iteration_id": current_iteration["id"],
            "title": f"Runtime Defer Requirement {uuid4().hex[:8]}",
            "owner_id": owner_id,
        },
    ).json()
    db = SessionLocal()
    try:
        db.query(Requirement).filter(Requirement.id == requirement["id"]).update({"status": "active"})
        db.commit()
    finally:
        db.close()
    requirement["status"] = "active"
    task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "requirement_id": requirement["id"],
            "iteration_id": current_iteration["id"],
            "title": f"Runtime Defer Task {uuid4().hex[:8]}",
            "status": "doing",
        },
    ).json()
    test_case = client.post(
        "/api/v1/test-cases",
        json={
            "project_id": project_id,
            "requirement_id": requirement["id"],
            "iteration_id": current_iteration["id"],
            "title": f"Runtime Defer Case {uuid4().hex[:8]}",
        },
    ).json()

    deferred = client.post(
        f"/api/v1/workflow-runtime/requirement/{requirement['id']}/transition",
        json={"action_key": "defer", "payload": {"target_iteration_id": target_iteration["id"], "remark": "move"}},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert deferred.status_code == 200
    assert deferred.json()["status"] == "draft"
    assert client.get(f"/api/v1/requirements/{requirement['id']}").json()["iteration_id"] == target_iteration["id"]
    assert client.get(f"/api/v1/tasks/{task['id']}").json()["iteration_id"] == target_iteration["id"]
    assert client.get(f"/api/v1/test-cases/{test_case['id']}").json()["iteration_id"] == target_iteration["id"]


def test_runtime_routes_bug_type_to_target_status_and_records_resolution(client: TestClient):
    _, project_id = _create_project_with_bug_workflow(client)
    developer_id, developer_token = _create_user("Bug Router", "developer")
    _add_project_member(project_id, developer_id, "developer")
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "title": f"Bug route {uuid4().hex[:8]}", "owner_id": developer_id},
    ).json()

    executed = client.post(
        f"/api/v1/workflow-runtime/bug/{bug['id']}/transition",
        json={
            "action_key": "confirm_bug_type",
            "payload": {"selected_values": {"bug_type": "code_issue"}},
        },
        headers={"Authorization": f"Bearer {developer_token}"},
    )

    assert executed.status_code == 200
    assert executed.json()["status"] == "fixing"
    assert executed.json()["resolved_target_status"] == "fixing"
    history = client.get(f"/api/v1/bugs/{bug['id']}/status-operations").json()
    assert history[-1]["resolved_target_status"] == "fixing"
    assert history[-1]["selected_values"]["bug_type"] == "code_issue"


def test_runtime_submit_confirmation_moves_bug_fix_task_to_confirmation_handler(client: TestClient):
    config = client.post(
        "/api/v1/assignee-rule-configs",
        json={
            "name": f"Task Runtime Config {uuid4().hex[:8]}",
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
        json={"name": f"Task Runtime Project {uuid4().hex[:8]}", "assignee_rule_config_id": config.json()["id"]},
    )
    assert project.status_code == 200
    developer_id, developer_token = _create_user("Task Runtime Developer", "developer")
    confirmer_id, _ = _create_user("Task Runtime Owner", "project_owner")
    _add_project_member(project.json()["id"], developer_id, "developer")
    _add_project_member(project.json()["id"], confirmer_id, "project_owner")
    task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project.json()["id"],
            "title": f"Task runtime {uuid4().hex[:8]}",
            "task_type": "bug_fix",
            "owner_id": developer_id,
        },
    ).json()

    executed = client.post(
        f"/api/v1/workflow-runtime/task/{task['id']}/transition",
        json={"action_key": "submit_confirmation", "payload": {"remark": "ready for review"}},
        headers={"Authorization": f"Bearer {developer_token}"},
    )

    assert executed.status_code == 200
    assert executed.json()["status"] == "pending_confirmation"
    assert executed.json()["owner_id"] == confirmer_id
