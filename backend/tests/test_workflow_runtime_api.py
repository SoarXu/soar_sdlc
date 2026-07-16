from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.session import SessionLocal
from app.models.bug import Bug
from app.models.notification import Notification
from app.models.project_member import ProjectMember
from app.models.relation import ObjectRelation
from app.models.requirement import Requirement
from app.models.role import Role, UserRole
from app.models.test_run import TestRun as RunModel
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


def _create_system_template_scheme(client: TestClient, name: str, **role_fields) -> dict:
    response = client.post(
        "/api/v1/assignee-rule-configs",
        json={
            "name": name,
            "creation_mode": "template",
            "template_source": {"source_type": "system", "source_id": "system-standard"},
            **role_fields,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _scheme_definition(client: TestClient, config_id: int, object_type: str) -> dict:
    definitions = client.get(
        f"/api/v1/workflow-definitions?scope_type=assignee_rule_config&scope_id={config_id}"
    ).json()
    return next(item for item in definitions if item["object_type"] == object_type)


def _enable_scheme(client: TestClient, config_id: int) -> None:
    response = client.post(f"/api/v1/assignee-rule-configs/{config_id}/enable")
    assert response.status_code == 200, response.text


def test_runtime_discovers_executes_and_audits_transitions_by_state_id(client: TestClient):
    project = client.post("/api/v1/projects", json={"name": f"ID Runtime Project {uuid4().hex[:8]}"}).json()
    user_id, token = _create_user("ID Runtime Member", "project_member")
    _add_project_member(project["id"], user_id, "project_member")
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "title": "ID runtime requirement"},
        headers={"Authorization": f"Bearer {token}"},
    ).json()

    actions = client.get(
        f"/api/v1/workflow-runtime/requirement/{requirement['id']}/transitions",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert actions.status_code == 200
    claim = next(item for item in actions.json() if item["action_key"] == "claim")
    assert claim["from_state_id"] == requirement["current_state_id"]
    assert claim["to_state_id"] != claim["from_state_id"]

    executed = client.post(
        f"/api/v1/workflow-runtime/requirement/{requirement['id']}/transition",
        json={"action_key": "claim"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert executed.status_code == 200, executed.text
    assert executed.json()["current_state_id"] == claim["to_state_id"]
    assert executed.json()["status_name"] == "处理中"
    loaded = client.get(f"/api/v1/requirements/{requirement['id']}").json()
    assert loaded["current_state_id"] == claim["to_state_id"]
    assert loaded["status_name"] == "处理中"

    history = client.get(f"/api/v1/requirements/{requirement['id']}/status-operations").json()
    operation = history[-1]
    assert operation["workflow_definition_id"] == requirement["workflow_definition_id"]
    assert operation["from_state_id"] == claim["from_state_id"]
    assert operation["to_state_id"] == claim["to_state_id"]
    assert operation["from_state_name"] == "待分派"
    assert operation["to_state_name"] == "处理中"


def _create_project_with_bug_workflow(client: TestClient) -> tuple[int, int]:
    _create_user("Runtime Developer Role Seed", "developer")
    config = client.post(
        "/api/v1/assignee-rule-configs",
        json={
            "name": f"Runtime Config {uuid4().hex[:8]}",
            "requirement_owner_roles": "",
            "task_owner_roles": "",
            "test_case_tester_roles": "tester",
            "test_run_owner_roles": "tester",
            "bug_owner_roles": "",
            "creation_mode": "template",
            "template_source": {"source_type": "system", "source_id": "system-standard"},
        },
    )
    assert config.status_code == 201
    definitions = client.get(
        f"/api/v1/workflow-definitions?scope_type=assignee_rule_config&scope_id={config.json()['id']}"
    ).json()
    definition = next(item for item in definitions if item["object_type"] == "bug")
    graph = client.put(
        f"/api/v1/workflow-definitions/{definition['id']}/graph",
        json={
            "initial_state_id": -1,
            "states": [
                {"id": -1, "status_name": "Pending", "category": "start", "x": 100, "y": 100},
                {"id": -2, "status_name": "Fixing", "category": "normal", "x": 300, "y": 100},
                {"id": -3, "status_name": "Closed", "category": "terminal", "x": 500, "y": 100},
            ],
            "transitions": [
                {
                    "action_key": "start_fixing",
                    "action_name": "确认",
                    "from_state_id": -1,
                    "to_state_id": -2,
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
                    "from_state_id": -1,
                    "to_state_id": -3,
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
    enabled = client.post(f"/api/v1/assignee-rule-configs/{config.json()['id']}/enable")
    assert enabled.status_code == 200, enabled.text
    project = client.post(
        "/api/v1/projects",
        json={"name": f"Runtime Project {uuid4().hex[:8]}", "assignee_rule_config_id": config.json()["id"]},
    )
    assert project.status_code == 200
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
            "creation_mode": "template",
            "template_source": {"source_type": "system", "source_id": "system-standard"},
        },
    )
    assert config.status_code == 201
    definitions = client.get(
        f"/api/v1/workflow-definitions?scope_type=assignee_rule_config&scope_id={config.json()['id']}"
    ).json()
    definition = next(item for item in definitions if item["object_type"] == "requirement")
    graph = client.put(
        f"/api/v1/workflow-definitions/{definition['id']}/graph",
        json={
            "initial_state_id": -1,
            "states": [
                {"id": -1, "status_name": "Pending Assignment", "category": "start", "x": 100, "y": 100},
                {"id": -2, "status_name": "Processing", "category": "normal", "x": 300, "y": 100},
            ],
            "transitions": [
                {
                    "action_key": "claim",
                    "action_name": "认领",
                    "from_state_id": -1,
                    "to_state_id": -2,
                    "allowed_roles": "project_member",
                    "handler_rule": {"target_type": "actor", "fallback_type": "keep_current"},
                },
                {
                    "action_key": "defer",
                    "action_name": "延期",
                    "from_state_id": -2,
                    "to_state_id": -1,
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
    enabled = client.post(f"/api/v1/assignee-rule-configs/{config.json()['id']}/enable")
    assert enabled.status_code == 200, enabled.text
    project = client.post(
        "/api/v1/projects",
        json={"name": f"Runtime Requirement Project {uuid4().hex[:8]}", "assignee_rule_config_id": config.json()["id"]},
    )
    assert project.status_code == 200
    return config.json()["id"], project.json()["id"]


def test_runtime_lists_configured_transitions_and_batch(client: TestClient):
    _, project_id = _create_project_with_bug_workflow(client)
    owner_id, _ = _create_user("Runtime Listed Owner", "developer")
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "title": f"Runtime Bug {uuid4().hex[:8]}", "owner_id": owner_id},
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
    owner_id, _ = _create_user("Runtime Manual Flag Owner", "developer")
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "title": f"Manual Owner Bug {uuid4().hex[:8]}", "owner_id": owner_id},
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


def test_runtime_executes_notification_trigger_and_post_action_with_audit_result(client: TestClient):
    _, project_id = _create_project_with_bug_workflow(client)
    owner_id, token = _create_user("Runtime Automation Owner", "developer")
    _add_project_member(project_id, owner_id, "developer")
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "title": f"Automation Bug {uuid4().hex[:8]}", "owner_id": owner_id},
    ).json()
    db = SessionLocal()
    try:
        transition = db.query(WorkflowTransition).filter(WorkflowTransition.action_key == "start_fixing").order_by(WorkflowTransition.id.desc()).first()
        transition.trigger_config = {
            "type": "notification",
            "receiver": "actor",
            "title": "Workflow started",
        }
        transition.post_action_config = {
            "type": "notification",
            "receiver": "next_handler",
            "title": "Work item assigned",
        }
        db.commit()
    finally:
        db.close()

    executed = client.post(
        f"/api/v1/workflow-runtime/bug/{bug['id']}/transition",
        json={"action_key": "start_fixing"},
        headers={"Authorization": f"Bearer {token}"},
    )
    history = client.get(f"/api/v1/bugs/{bug['id']}/status-operations").json()

    assert executed.status_code == 200
    assert [item["stage"] for item in history[-1]["selected_values"]["automation_results"]] == ["trigger", "post_action"]
    db = SessionLocal()
    try:
        titles = {
            item.title
            for item in db.query(Notification).filter(
                Notification.object_type == "bug",
                Notification.object_id == bug["id"],
            ).all()
        }
    finally:
        db.close()
    assert {"Workflow started", "Work item assigned"} <= titles


def test_runtime_rejects_unsupported_historical_component_without_mutation(client: TestClient):
    _, project_id = _create_project_with_bug_workflow(client)
    owner_id, token = _create_user("Runtime Invalid Config Owner", "developer")
    _add_project_member(project_id, owner_id, "developer")
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "title": f"Invalid Config Bug {uuid4().hex[:8]}", "owner_id": owner_id},
    ).json()
    db = SessionLocal()
    try:
        transition = db.query(WorkflowTransition).filter(WorkflowTransition.action_key == "start_fixing").order_by(WorkflowTransition.id.desc()).first()
        transition.trigger_config = {"type": "legacy_script"}
        db.commit()
    finally:
        db.close()

    executed = client.post(
        f"/api/v1/workflow-runtime/bug/{bug['id']}/transition",
        json={"action_key": "start_fixing"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert executed.status_code == 422
    assert client.get(f"/api/v1/bugs/{bug['id']}").json()["status"] == bug["status"]


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
    assert executed.json()["status_name"] == "Fixing"
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
    claimed = client.post(
        f"/api/v1/workflow-runtime/requirement/{requirement['id']}/transition",
        json={"action_key": "claim"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert claimed.status_code == 200, claimed.text
    task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "requirement_id": requirement["id"],
            "iteration_id": current_iteration["id"],
            "title": f"Runtime Defer Task {uuid4().hex[:8]}",
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
    assert deferred.json()["status_name"] == "Pending Assignment"
    assert client.get(f"/api/v1/requirements/{requirement['id']}").json()["iteration_id"] == target_iteration["id"]
    assert client.get(f"/api/v1/tasks/{task['id']}").json()["iteration_id"] == target_iteration["id"]
    assert client.get(f"/api/v1/test-cases/{test_case['id']}").json()["iteration_id"] == target_iteration["id"]


def test_runtime_routes_bug_type_to_target_status_and_records_resolution(client: TestClient):
    project_id = client.post(
        "/api/v1/projects",
        json={"name": f"Default Bug Routing Project {uuid4().hex[:8]}"},
    ).json()["id"]
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


def test_bug_routing_modes_reject_forged_targets_and_audit_reclassification(client: TestClient):
    project_id = client.post(
        "/api/v1/projects",
        json={"name": f"Routing Mode Project {uuid4().hex[:8]}"},
    ).json()["id"]
    handler_id, handler_token = _create_user("Routing Mode Handler", "developer")
    manager_id, manager_token = _create_user("Routing Mode Manager", "project_owner")
    _add_project_member(project_id, handler_id, "developer")
    _add_project_member(project_id, manager_id, "project_owner")

    automatic_bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "title": f"Automatic Bug {uuid4().hex[:8]}", "owner_id": handler_id},
    ).json()
    forged_automatic = client.post(
        f"/api/v1/workflow-runtime/bug/{automatic_bug['id']}/transition",
        json={
            "action_key": "confirm_bug_type",
            "selected_target_status": "pending_verification",
            "payload": {"selected_values": {"bug_type": "code_issue"}},
        },
        headers={"Authorization": f"Bearer {handler_token}"},
    )
    assert forged_automatic.status_code == 422
    assert client.get(f"/api/v1/bugs/{automatic_bug['id']}").json()["status"] == "pending_handling"

    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "title": f"Override Bug {uuid4().hex[:8]}", "owner_id": handler_id},
    ).json()
    confirmed = client.post(
        f"/api/v1/workflow-runtime/bug/{bug['id']}/transition",
        json={"action_key": "confirm_bug_type", "payload": {"selected_values": {"bug_type": "code_issue"}}},
        headers={"Authorization": f"Bearer {handler_token}"},
    )
    assert confirmed.status_code == 200

    forbidden_override = client.post(
        f"/api/v1/workflow-runtime/bug/{bug['id']}/transition",
        json={
            "action_key": "reclassify_bug_type",
            "selected_target_status": "pending_verification",
            "override_reason": "force verification",
            "payload": {"reason": "classification review", "selected_values": {"bug_type": "configuration_issue"}},
        },
        headers={"Authorization": f"Bearer {handler_token}"},
    )
    assert forbidden_override.status_code == 403

    db = SessionLocal()
    try:
        stored = db.query(Bug).filter(Bug.id == bug["id"]).one()
        stored.owner_id = manager_id
        stored.status = "fixing"
        stored.bug_type = "code_issue"
        db.commit()
    finally:
        db.close()

    allowed_override = client.post(
        f"/api/v1/workflow-runtime/bug/{bug['id']}/transition",
        json={
            "action_key": "reclassify_bug_type",
            "selected_target_status": "fixing",
            "override_reason": "keep repair active",
            "payload": {"reason": "duplicate evidence needs repair", "selected_values": {"bug_type": "duplicate_issue"}},
        },
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert allowed_override.status_code == 200
    assert allowed_override.json()["default_target_status"] == "pending_verification"
    assert allowed_override.json()["resolved_target_status"] == "fixing"
    history = client.get(f"/api/v1/bugs/{bug['id']}/status-operations").json()
    operation = history[-1]
    assert operation["reason"] == "duplicate evidence needs repair"
    assert operation["override_reason"] == "keep repair active"
    assert operation["selected_values"]["old_bug_type"] == "code_issue"
    assert operation["selected_values"]["new_bug_type"] == "duplicate_issue"
    assert operation["selected_values"]["old_status"] == "fixing"
    assert operation["selected_values"]["default_target_status"] == "pending_verification"
    assert operation["selected_values"]["resolved_target_status"] == "fixing"


def test_manual_routing_mode_requires_an_allowed_target_status(client: TestClient):
    config = _create_system_template_scheme(client, f"Manual Routing Config {uuid4().hex[:8]}")
    definition = _scheme_definition(client, config["id"], "bug")
    graph = client.put(
        f"/api/v1/workflow-definitions/{definition['id']}/graph",
        json={
            "initial_state_id": -1,
            "states": [
                {"id": -1, "status_name": "Pending", "category": "start", "x": 100, "y": 100},
                {"id": -2, "status_name": "Fixing", "category": "normal", "x": 300, "y": 100},
                {"id": -3, "status_name": "Verify", "category": "normal", "x": 500, "y": 100},
            ],
            "transitions": [
                {
                    "action_key": "confirm_bug_type",
                    "action_name": "Manual classification",
                    "from_state_id": -1,
                    "to_state_id": -2,
                    "handler_rule": {"target_type": "keep_current", "fallback_type": "keep_current"},
                    "condition_config": {
                        "routing_mode": "manual_allowed",
                        "field": "bug_type",
                        "routes": {"code_issue": -2, "duplicate_issue": -3},
                    },
                    "form_config": {
                        "fields": [{"field": "bug_type", "label": "Bug Type", "type": "select", "required": True}]
                    },
                }
            ],
        },
    )
    assert graph.status_code == 200
    verify_state_id = next(item["id"] for item in graph.json()["states"] if item["status_name"] == "Verify")
    fixing_state_id = next(item["id"] for item in graph.json()["states"] if item["status_name"] == "Fixing")
    _enable_scheme(client, config["id"])
    project = client.post(
        "/api/v1/projects",
        json={"name": f"Manual Routing Project {uuid4().hex[:8]}", "assignee_rule_config_id": config["id"]},
    ).json()
    handler_id, handler_token = _create_user("Manual Routing Handler", "developer")
    _add_project_member(project["id"], handler_id, "developer")

    first_bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project["id"], "title": f"Manual Missing Target {uuid4().hex[:8]}", "owner_id": handler_id},
    ).json()
    missing_target = client.post(
        f"/api/v1/workflow-runtime/bug/{first_bug['id']}/transition",
        json={"action_key": "confirm_bug_type", "payload": {"selected_values": {"bug_type": "code_issue"}}},
        headers={"Authorization": f"Bearer {handler_token}"},
    )
    assert missing_target.status_code == 422

    second_bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project["id"], "title": f"Manual Selected Target {uuid4().hex[:8]}", "owner_id": handler_id},
    ).json()
    selected = client.post(
        f"/api/v1/workflow-runtime/bug/{second_bug['id']}/transition",
        json={
            "action_key": "confirm_bug_type",
            "selected_target_state_id": verify_state_id,
            "payload": {"selected_values": {"bug_type": "code_issue"}},
        },
        headers={"Authorization": f"Bearer {handler_token}"},
    )
    assert selected.status_code == 200
    assert selected.json()["default_target_state_id"] == fixing_state_id
    assert selected.json()["resolved_target_state_id"] == verify_state_id
    assert selected.json()["status_name"] == "Verify"


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
            "creation_mode": "template",
            "template_source": {"source_type": "system", "source_id": "system-standard"},
        },
    )
    assert config.status_code == 201
    _enable_scheme(client, config.json()["id"])
    project = client.post(
        "/api/v1/projects",
        json={"name": f"Task Runtime Project {uuid4().hex[:8]}", "assignee_rule_config_id": config.json()["id"]},
    )
    assert project.status_code == 200
    developer_id, developer_token = _create_user("Task Runtime Developer", "developer")
    confirmer_id, confirmer_token = _create_user("Task Runtime Owner", "project_owner")
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

    claimed = client.post(
        f"/api/v1/workflow-runtime/task/{task['id']}/transition",
        json={"action_key": "claim"},
        headers={"Authorization": f"Bearer {developer_token}"},
    )
    assert claimed.status_code == 200, claimed.text

    executed = client.post(
        f"/api/v1/workflow-runtime/task/{task['id']}/transition",
        json={"action_key": "submit_confirmation", "payload": {"remark": "ready for review"}},
        headers={"Authorization": f"Bearer {developer_token}"},
    )

    assert executed.status_code == 200
    assert executed.json()["status"] == "pending_confirmation"
    assert executed.json()["owner_id"] == confirmer_id
    returned = client.post(
        f"/api/v1/workflow-runtime/task/{task['id']}/transition",
        json={"action_key": "return_rework", "payload": {"reason": "needs rework"}},
        headers={"Authorization": f"Bearer {confirmer_token}"},
    )
    assert returned.status_code == 200
    assert returned.json()["status"] == "in_processing"
    assert returned.json()["owner_id"] == developer_id
    history = client.get(f"/api/v1/tasks/{task['id']}/status-operations").json()
    submit_operation = next(item for item in history if item["action"] == "submit_confirmation")
    routing = submit_operation["selected_values"]["handler_routing"]
    assert routing["previous_owner_id"] == developer_id
    assert routing["resolved_default_owner_id"] == confirmer_id
    assert routing["final_owner_id"] == confirmer_id
    assert routing["manual_override"] is False


def test_ownerless_runtime_actions_require_project_membership_and_allow_system_admin(client: TestClient):
    project = client.post(
        "/api/v1/projects",
        json={"name": f"Runtime Permission Project {uuid4().hex[:8]}"},
    ).json()
    member_id, member_token = _create_user("Runtime Claim Member", "developer")
    outsider_id, outsider_token = _create_user("Runtime Claim Outsider", "developer")
    admin_id, admin_token = _create_user("Runtime Assignment Admin", "system_admin")
    _add_project_member(project["id"], member_id, "developer")

    claim_task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project["id"],
            "title": f"Runtime Claim Task {uuid4().hex[:8]}",
            "task_type": "standalone_operation",
            "owner_id": None,
        },
    ).json()
    assign_task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project["id"],
            "title": f"Runtime Assign Task {uuid4().hex[:8]}",
            "task_type": "standalone_operation",
            "owner_id": None,
        },
    ).json()

    outsider_actions = client.get(
        f"/api/v1/workflow-runtime/task/{claim_task['id']}/transitions",
        headers={"Authorization": f"Bearer {outsider_token}"},
    )
    outsider_claim = client.post(
        f"/api/v1/workflow-runtime/task/{claim_task['id']}/transition",
        json={"action_key": "claim"},
        headers={"Authorization": f"Bearer {outsider_token}"},
    )
    member_actions = client.get(
        f"/api/v1/workflow-runtime/task/{claim_task['id']}/transitions",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    member_claim = client.post(
        f"/api/v1/workflow-runtime/task/{claim_task['id']}/transition",
        json={"action_key": "claim"},
        headers={"Authorization": f"Bearer {member_token}"},
    )
    admin_actions = client.get(
        f"/api/v1/workflow-runtime/task/{assign_task['id']}/transitions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    admin_assign = client.post(
        f"/api/v1/workflow-runtime/task/{assign_task['id']}/transition",
        json={"action_key": "assign", "next_owner_id": member_id, "payload": {"reason": "admin assignment"}},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert outsider_id != member_id
    assert outsider_actions.status_code == 200
    assert outsider_actions.json() == []
    assert outsider_claim.status_code == 403
    assert "claim" in {item["action_key"] for item in member_actions.json()}
    assert member_claim.status_code == 200
    assert member_claim.json()["owner_id"] == member_id
    assert "assign" in {item["action_key"] for item in admin_actions.json()}
    assert admin_assign.status_code == 200
    assert admin_assign.json()["owner_id"] == member_id
    assert admin_assign.json()["status"] == "in_processing"


def test_scoped_workflow_does_not_fallback_to_system_action(client: TestClient):
    config = _create_system_template_scheme(client, f"Authoritative Workflow {uuid4().hex[:8]}")
    _enable_scheme(client, config["id"])
    project = client.post(
        "/api/v1/projects",
        json={
            "name": f"Authoritative Project {uuid4().hex[:8]}",
            "assignee_rule_config_id": config["id"],
        },
    ).json()
    definition = _scheme_definition(client, config["id"], "task")
    graph = client.put(
        f"/api/v1/workflow-definitions/{definition['id']}/graph",
        json={
            "initial_state_id": -1,
            "states": [
                {
                    "id": -1,
                    "status_name": "Pending Assignment",
                    "category": "start",
                    "x": 100,
                    "y": 100,
                }
            ],
            "transitions": [],
        },
    )
    assert graph.status_code == 200
    member_id, member_token = _create_user("Authoritative Member", "developer")
    _add_project_member(project["id"], member_id, "developer")
    task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project["id"],
            "title": f"Authoritative Task {uuid4().hex[:8]}",
            "task_type": "standalone_operation",
            "owner_id": None,
        },
    ).json()

    listed = client.get(
        f"/api/v1/workflow-runtime/task/{task['id']}/transitions",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    executed = client.post(
        f"/api/v1/workflow-runtime/task/{task['id']}/transition",
        json={"action_key": "claim"},
        headers={"Authorization": f"Bearer {member_token}"},
    )

    assert listed.status_code == 200
    assert listed.json() == []
    assert executed.status_code == 400
    assert "not available" in executed.json()["detail"].lower()


def test_runtime_owner_transfer_and_admin_change_handler_are_atomic_and_audited(client: TestClient):
    project = client.post(
        "/api/v1/projects",
        json={"name": f"Ownership Runtime Project {uuid4().hex[:8]}"},
    ).json()
    handler_id, handler_token = _create_user("Ownership Runtime Handler", "developer")
    target_id, _ = _create_user("Ownership Runtime Target", "developer")
    admin_id, admin_token = _create_user("Ownership Runtime Admin", "system_admin")
    _add_project_member(project["id"], handler_id, "developer")
    _add_project_member(project["id"], target_id, "developer")
    task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project["id"],
            "title": f"Ownership Runtime Task {uuid4().hex[:8]}",
            "task_type": "standalone_operation",
            "owner_id": handler_id,
        },
    ).json()
    claimed = client.post(
        f"/api/v1/workflow-runtime/task/{task['id']}/transition",
        json={"action_key": "claim"},
        headers={"Authorization": f"Bearer {handler_token}"},
    )
    assert claimed.status_code == 200, claimed.text

    transferred = client.post(
        f"/api/v1/workflow-runtime/task/{task['id']}/transition",
        json={
            "action_key": "transfer",
            "next_owner_id": target_id,
            "payload": {"reason": "handoff for implementation"},
        },
        headers={"Authorization": f"Bearer {handler_token}"},
    )
    changed = client.post(
        f"/api/v1/workflow-runtime/task/{task['id']}/transition",
        json={
            "action_key": "change_handler",
            "next_owner_id": handler_id,
            "delegate_reason": "administrative correction",
            "payload": {"reason": "restore original handler"},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert transferred.status_code == 200
    assert transferred.json()["status"] == "in_processing"
    assert transferred.json()["owner_id"] == target_id
    assert changed.status_code == 200
    assert changed.json()["status"] == "in_processing"
    assert changed.json()["owner_id"] == handler_id
    history = client.get(f"/api/v1/tasks/{task['id']}/status-operations").json()
    transfer_operation = next(item for item in history if item["action"] == "transfer")
    change_operation = next(item for item in history if item["action"] == "change_handler")
    assert transfer_operation["from_status"] == transfer_operation["to_status"] == "in_processing"
    assert transfer_operation["actor_id"] == handler_id
    assert transfer_operation["reason"] == "handoff for implementation"
    assert transfer_operation["next_owner_id"] == target_id
    assert f"{handler_id} -> {target_id}" in transfer_operation["remark"]
    assert change_operation["actor_id"] == admin_id
    assert change_operation["reason"] == "restore original handler"
    assert change_operation["next_owner_id"] == handler_id
    assert change_operation["delegate_reason"] == "administrative correction"
    assert f"{target_id} -> {handler_id}" in change_operation["remark"]


def test_bug_from_test_execution_routes_repair_and_verification_handlers_separately(client: TestClient):
    project = client.post(
        "/api/v1/projects",
        json={"name": f"Test Source Routing Project {uuid4().hex[:8]}"},
    ).json()
    repair_id, repair_token = _create_user("Test Source Repair", "developer")
    default_tester_id, _ = _create_user("Test Source Default Tester", "tester")
    executor_id, executor_token = _create_user("Test Source Executor", "tester")
    _add_project_member(project["id"], repair_id, "developer")
    _add_project_member(project["id"], default_tester_id, "tester", sort_order=0)
    _add_project_member(project["id"], executor_id, "tester", sort_order=10)
    requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project["id"],
            "title": f"Test Source Requirement {uuid4().hex[:8]}",
            "owner_id": repair_id,
        },
    ).json()
    test_case = client.post(
        "/api/v1/test-cases",
        json={
            "project_id": project["id"],
            "requirement_id": requirement["id"],
            "title": f"Test Source Case {uuid4().hex[:8]}",
            "default_tester_id": default_tester_id,
        },
        headers={"Authorization": f"Bearer {executor_token}"},
    ).json()
    execution = client.post(
        f"/api/v1/test-cases/{test_case['id']}/executions",
        json={"steps_result_json": [{"result": "failed", "actual": "failure"}]},
        headers={"Authorization": f"Bearer {executor_token}"},
    )
    assert execution.status_code == 200
    bug = client.post(
        f"/api/v1/test-cases/{test_case['id']}/bugs",
        json={"title": f"Test Source Bug {uuid4().hex[:8]}", "bug_type": "code_issue"},
        headers={"Authorization": f"Bearer {executor_token}"},
    )
    assert bug.status_code == 200
    assert bug.json()["owner_id"] == repair_id
    assert bug.json()["reporter_id"] == executor_id

    classified = client.post(
        f"/api/v1/workflow-runtime/bug/{bug.json()['id']}/transition",
        json={"action_key": "confirm_bug_type", "payload": {"selected_values": {"bug_type": "code_issue"}}},
        headers={"Authorization": f"Bearer {repair_token}"},
    )
    submitted = client.post(
        f"/api/v1/workflow-runtime/bug/{bug.json()['id']}/transition",
        json={"action_key": "submit_verification", "payload": {"reason": "fixed"}},
        headers={"Authorization": f"Bearer {repair_token}"},
    )
    failed = client.post(
        f"/api/v1/workflow-runtime/bug/{bug.json()['id']}/transition",
        json={"action_key": "verification_failed", "payload": {"reason": "still reproducible"}},
        headers={"Authorization": f"Bearer {executor_token}"},
    )

    assert classified.status_code == 200
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "pending_verification"
    assert submitted.json()["owner_id"] == executor_id
    assert failed.status_code == 200
    assert failed.json()["status"] == "pending_handling"
    assert failed.json()["owner_id"] == repair_id
    history = client.get(f"/api/v1/bugs/{bug.json()['id']}/status-operations").json()
    submit_operation = next(item for item in history if item["action"] == "submit_verification")
    routing = submit_operation["selected_values"]["handler_routing"]
    assert routing["source_rule"] == "bug_verifier:test_executor"
    assert routing["previous_owner_id"] == repair_id
    assert routing["resolved_default_owner_id"] == executor_id


def test_submit_confirmation_blocks_when_no_confirmation_handler_resolves(client: TestClient):
    project = client.post(
        "/api/v1/projects",
        json={"name": f"Missing Confirmer Project {uuid4().hex[:8]}"},
    ).json()
    developer_id, developer_token = _create_user("Missing Confirmer Developer", "developer")
    _add_project_member(project["id"], developer_id, "developer")
    task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project["id"],
            "title": f"Missing Confirmer Task {uuid4().hex[:8]}",
            "task_type": "bug_fix",
            "owner_id": developer_id,
        },
    ).json()
    claimed = client.post(
        f"/api/v1/workflow-runtime/task/{task['id']}/transition",
        json={"action_key": "claim"},
        headers={"Authorization": f"Bearer {developer_token}"},
    )
    assert claimed.status_code == 200, claimed.text

    response = client.post(
        f"/api/v1/workflow-runtime/task/{task['id']}/transition",
        json={"action_key": "submit_confirmation", "payload": {"reason": "ready"}},
        headers={"Authorization": f"Bearer {developer_token}"},
    )

    assert response.status_code == 422
    unchanged = client.get(f"/api/v1/tasks/{task['id']}").json()
    assert unchanged["status"] == "in_processing"
    assert unchanged["owner_id"] == developer_id


def test_task_confirmation_routes_all_branches_and_records_manual_override(client: TestClient):
    config = client.post(
        "/api/v1/assignee-rule-configs",
        json={
            "name": f"Branch Confirmation Config {uuid4().hex[:8]}",
            "requirement_owner_roles": "product_owner",
            "task_owner_roles": "developer",
            "test_case_tester_roles": "tester",
            "test_run_owner_roles": "tester",
            "bug_owner_roles": "developer",
            "creation_mode": "template",
            "template_source": {"source_type": "system", "source_id": "system-standard"},
        },
    ).json()
    task_definition = _scheme_definition(client, config["id"], "task")
    graph = client.put(
        f"/api/v1/workflow-definitions/{task_definition['id']}/graph",
        json={
            "initial_state_id": -1,
            "states": [
                {"id": -1, "status_name": "Pending Assignment", "category": "start"},
                {"id": -2, "status_name": "In Processing", "category": "normal"},
                {"id": -3, "status_name": "Pending Confirmation", "category": "normal"},
            ],
            "transitions": [
                {
                    "action_key": "claim",
                    "action_name": "Claim",
                    "from_state_id": -1,
                    "to_state_id": -2,
                    "allowed_roles": "project_member",
                    "handler_rule": {"target_type": "actor", "fallback_type": "keep_current"},
                },
                {
                    "action_key": "submit_confirmation",
                    "action_name": "Submit Confirmation",
                    "from_state_id": -2,
                    "to_state_id": -3,
                    "handler_rule": {
                        "target_type": "task_confirmation",
                        "fallback_type": "project_role",
                        "fallback_roles": "project_owner",
                        "allow_manual_owner": True,
                    },
                },
            ],
        },
    )
    assert graph.status_code == 200, graph.text
    _enable_scheme(client, config["id"])
    project = client.post(
        "/api/v1/projects",
        json={"name": f"Branch Confirmation Project {uuid4().hex[:8]}", "assignee_rule_config_id": config["id"]},
    ).json()
    executor_id, executor_token = _create_user("Branch Executor", "developer")
    requirement_owner_id, _ = _create_user("Branch Requirement Owner", "product_owner")
    bug_reporter_id, _ = _create_user("Branch Bug Reporter", "tester")
    test_owner_id, _ = _create_user("Branch Test Owner", "tester")
    standalone_creator_id, standalone_creator_token = _create_user("Branch Standalone Creator", "developer")
    manual_owner_id, _ = _create_user("Branch Manual Confirmer", "tester")
    for index, (user_id, role) in enumerate(
        [
            (executor_id, "developer"),
            (requirement_owner_id, "product_owner"),
            (bug_reporter_id, "tester"),
            (test_owner_id, "tester"),
            (standalone_creator_id, "developer"),
            (manual_owner_id, "tester"),
        ]
    ):
        _add_project_member(project["id"], user_id, role, sort_order=index)

    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "title": f"Branch Requirement {uuid4().hex[:8]}", "owner_id": requirement_owner_id},
    ).json()
    requirement_task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project["id"],
            "requirement_id": requirement["id"],
            "title": f"Requirement Branch Task {uuid4().hex[:8]}",
            "task_type": "requirement_implementation",
            "owner_id": executor_id,
        },
    ).json()
    bug_task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project["id"],
            "title": f"Bug Branch Task {uuid4().hex[:8]}",
            "task_type": "bug_fix",
            "owner_id": executor_id,
        },
    ).json()
    client.post(
        "/api/v1/bugs",
        json={
            "project_id": project["id"],
            "task_id": bug_task["id"],
            "title": f"Branch Source Bug {uuid4().hex[:8]}",
            "reporter_id": bug_reporter_id,
            "owner_id": executor_id,
        },
    )
    test_task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project["id"],
            "title": f"Test Branch Task {uuid4().hex[:8]}",
            "task_type": "test_support",
            "owner_id": executor_id,
        },
    ).json()
    standalone_task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project["id"],
            "title": f"Standalone Branch Task {uuid4().hex[:8]}",
            "task_type": "standalone_operation",
            "owner_id": standalone_creator_id,
        },
        headers={"Authorization": f"Bearer {standalone_creator_token}"},
    ).json()
    manual_task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project["id"],
            "title": f"Manual Branch Task {uuid4().hex[:8]}",
            "task_type": "standalone_operation",
            "owner_id": standalone_creator_id,
        },
        headers={"Authorization": f"Bearer {standalone_creator_token}"},
    ).json()
    db = SessionLocal()
    try:
        test_run = RunModel(project_id=project["id"], name=f"Branch Test Run {uuid4().hex[:8]}", test_owner_id=test_owner_id)
        db.add(test_run)
        db.flush()
        db.add(
            ObjectRelation(
                source_type="test_run",
                source_id=test_run.id,
                target_type="task",
                target_id=test_task["id"],
                relation_type="linked_task",
                creator_id=executor_id,
            )
        )
        db.commit()
    finally:
        db.close()

    expected = [
        (requirement_task, executor_token, requirement_owner_id),
        (bug_task, executor_token, bug_reporter_id),
        (test_task, executor_token, test_owner_id),
        (standalone_task, standalone_creator_token, standalone_creator_id),
    ]
    for task, token, expected_owner_id in expected:
        claimed = client.post(
            f"/api/v1/workflow-runtime/task/{task['id']}/transition",
            json={"action_key": "claim"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert claimed.status_code == 200, claimed.text
        response = client.post(
            f"/api/v1/workflow-runtime/task/{task['id']}/transition",
            json={"action_key": "submit_confirmation", "payload": {"reason": "branch confirmation"}},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["owner_id"] == expected_owner_id

    manual_claimed = client.post(
        f"/api/v1/workflow-runtime/task/{manual_task['id']}/transition",
        json={"action_key": "claim"},
        headers={"Authorization": f"Bearer {standalone_creator_token}"},
    )
    assert manual_claimed.status_code == 200, manual_claimed.text
    manual = client.post(
        f"/api/v1/workflow-runtime/task/{manual_task['id']}/transition",
        json={
            "action_key": "submit_confirmation",
            "next_owner_id": manual_owner_id,
            "override_reason": "specialist review",
        },
        headers={"Authorization": f"Bearer {standalone_creator_token}"},
    )
    assert manual.status_code == 200
    assert manual.json()["owner_id"] == manual_owner_id
    operation = client.get(f"/api/v1/tasks/{manual_task['id']}/status-operations").json()[-1]
    routing = operation["selected_values"]["handler_routing"]
    assert routing["resolved_default_owner_id"] == standalone_creator_id
    assert routing["final_owner_id"] == manual_owner_id
    assert routing["manual_override"] is True
    assert routing["override_reason"] == "specialist review"
