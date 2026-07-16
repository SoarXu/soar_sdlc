from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import SessionLocal
from app.core.security import get_password_hash
from app.core.security import create_access_token
from app.models.user import User
from app.models.requirement import Requirement
from app.models.workflow_definition import WorkflowState


def _configure_and_enable_scheme(client: TestClient, config_id: int) -> None:
    definitions = client.get(
        f"/api/v1/workflow-definitions?scope_type=assignee_rule_config&scope_id={config_id}"
    ).json()
    by_object_type = {item["object_type"]: item for item in definitions}
    for object_type in ("requirement", "task", "bug"):
        assert client.post(
            f"/api/v1/workflow-definitions/{by_object_type[object_type]['id']}/apply-template"
        ).status_code == 200
    enabled = client.post(f"/api/v1/assignee-rule-configs/{config_id}/enable")
    assert enabled.status_code == 200, enabled.text


def test_program_crud_persists_to_database(client: TestClient):
    name = f"项目集-{uuid4().hex[:8]}"

    created = client.post(
        "/api/v1/programs",
        json={
            "name": name,
            "planned_start_date": "2026-06-10",
            "planned_end_date": "2026-12-31",
            "actual_start_date": "2026-06-11",
            "actual_end_date": "2026-12-30",
            "description": "API 创建",
        },
    )
    assert created.status_code == 200
    created_data = created.json()
    program_id = created_data["id"]
    assert created_data["planned_start_date"] == "2026-06-10"
    assert created_data["planned_end_date"] == "2026-12-31"
    assert created_data["actual_start_date"] == "2026-06-11"
    assert created_data["actual_end_date"] == "2026-12-30"
    assert created_data["is_long_term"] is False
    assert created_data["status"] == "planning"

    db = SessionLocal()
    try:
        stored = db.execute(
            text("select name, planned_start_date, planned_end_date, actual_start_date, actual_end_date, is_long_term from programs where id = :id"),
            {"id": program_id},
        ).one()
        assert stored.name == name
        assert str(stored.planned_start_date) == "2026-06-10"
        assert str(stored.planned_end_date) == "2026-12-31"
        assert str(stored.actual_start_date) == "2026-06-11"
        assert str(stored.actual_end_date) == "2026-12-30"
        assert stored.is_long_term == 0
    finally:
        db.close()

    updated = client.patch(f"/api/v1/programs/{program_id}", json={"is_long_term": True, "actual_end_date": "2027-01-10"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "planning"
    assert updated.json()["is_long_term"] is True
    assert updated.json()["planned_end_date"] is None
    assert updated.json()["actual_end_date"] == "2027-01-10"

    started = client.post(
        f"/api/v1/programs/{program_id}/start",
        json={"effective_time": "2026-06-10T09:00:00"},
    )
    assert started.status_code == 200
    assert started.json()["status"] == "active"

    suspended = client.post(f"/api/v1/programs/{program_id}/suspend")
    assert suspended.status_code == 200
    assert suspended.json()["status"] == "paused"

    restarted = client.post(
        f"/api/v1/programs/{program_id}/start",
        json={"remark": "重新启动项目集"},
    )
    assert restarted.status_code == 200
    assert restarted.json()["status"] == "active"

    history = client.get(f"/api/v1/programs/{program_id}/status-operations")
    assert history.status_code == 200
    history_data = history.json()
    assert any(item["action"] == "start" and item["remark"] == "重新启动项目集" for item in history_data)

    deleted = client.delete(f"/api/v1/programs/{program_id}")
    assert deleted.status_code == 204

    listed = client.get("/api/v1/programs")
    assert all(item["id"] != program_id for item in listed.json())


def test_program_status_options_are_served_by_backend(client: TestClient):
    response = client.get("/api/v1/programs/status-options")

    assert response.status_code == 200
    options = response.json()
    assert {"label": "已挂起", "value": "paused"} in options
    assert {"label": "长期维护", "value": "maintenance"} not in options


def test_project_crud_uses_prd_fields(client: TestClient):
    name = f"项目-{uuid4().hex[:8]}"

    created = client.post(
        "/api/v1/projects",
        json={
            "name": name,
            "end_date": "2026-12-31",
            "actual_start_date": "2026-07-01",
            "actual_end_date": "2026-11-30",
            "description": "项目 API 创建",
        },
    )
    assert created.status_code == 200
    project_id = created.json()["id"]
    assert created.json()["name"] == name
    assert created.json()["end_date"] == "2026-12-31"
    assert created.json()["actual_start_date"] == "2026-07-01"
    assert created.json()["actual_end_date"] == "2026-11-30"
    assert created.json()["is_long_term"] is False
    assert created.json()["status"] == "planning"
    assert "owner_id" in created.json()

    detail = client.get(f"/api/v1/projects/{project_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == project_id
    assert detail.json()["name"] == name

    updated = client.patch(f"/api/v1/projects/{project_id}", json={"description": "已更新", "is_long_term": True, "actual_end_date": "2026-12-15"})
    assert updated.status_code == 200
    assert updated.json()["description"] == "已更新"
    assert updated.json()["is_long_term"] is True
    assert updated.json()["end_date"] is None
    assert updated.json()["actual_end_date"] == "2026-12-15"

    started = client.post(
        f"/api/v1/projects/{project_id}/start",
        json={"effective_time": "2026-07-01T09:00:00"},
    )
    assert started.status_code == 200
    assert started.json()["status"] == "active"

    suspended = client.post(
        f"/api/v1/projects/{project_id}/suspend",
        json={"effective_time": "2026-06-10T11:32:50", "remark": "阶段性挂起"},
    )
    assert suspended.status_code == 200
    assert suspended.json()["status"] == "paused"

    restarted = client.post(f"/api/v1/projects/{project_id}/start")
    assert restarted.status_code == 200
    assert restarted.json()["status"] == "active"

    paused_again = client.post(f"/api/v1/projects/{project_id}/suspend")
    assert paused_again.status_code == 200
    assert paused_again.json()["status"] == "paused"

    closed = client.post(
        f"/api/v1/projects/{project_id}/close",
        json={"effective_time": "2026-07-10T18:00:00"},
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"

    activated = client.post(f"/api/v1/projects/{project_id}/activate")
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"

    history = client.get(f"/api/v1/projects/{project_id}/status-operations")
    assert history.status_code == 200
    assert any(item["action"] == "suspend" and item["remark"] == "阶段性挂起" for item in history.json())

    deleted = client.delete(f"/api/v1/projects/{project_id}")
    assert deleted.status_code == 204


def test_project_without_assignee_rule_leaves_default_assignees_empty(client: TestClient):
    db = SessionLocal()
    try:
        users = []
        for username in ["product_owner_api", "default_developer_api", "default_tester_api"]:
            user = User(
                username=f"{username}_{uuid4().hex[:6]}",
                full_name=username,
                password_hash=get_password_hash("User123456"),
                is_active=True,
            )
            db.add(user)
            db.flush()
            users.append(user)
        db.commit()
        product_owner_id, developer_id, tester_id = [user.id for user in users]
    finally:
        db.close()

    project = client.post("/api/v1/projects", json={"name": f"Team Defaults Project-{uuid4().hex[:8]}"}).json()
    project_id = project["id"]

    saved_members = client.put(
        f"/api/v1/projects/{project_id}/members",
        json=[
            {"user_id": product_owner_id, "project_role": "product_owner", "is_default_assignee": True, "sort_order": 0},
            {"user_id": developer_id, "project_role": "developer", "sort_order": 1},
            {"user_id": tester_id, "project_role": "tester", "sort_order": 2},
        ],
    )
    assert saved_members.status_code == 200
    members = saved_members.json()
    assert {item["project_role"] for item in members} == {"product_owner", "developer", "tester"}

    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": "Requirement has no default owner"},
    ).json()
    assert requirement["owner_id"] is None

    standalone_task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "title": "Standalone task has no default owner"},
    ).json()
    assert standalone_task["owner_id"] is None

    requirement_task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "requirement_id": requirement["id"], "title": "Requirement task has no default owner"},
    ).json()
    assert requirement_task["owner_id"] is None

    test_case = client.post(
        "/api/v1/test-cases",
        json={"project_id": project_id, "requirement_id": requirement["id"], "title": "Case has no default tester"},
    ).json()
    assert test_case["default_tester_id"] is None

    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "requirement_id": requirement["id"], "title": "Bug has no default owner"},
    ).json()
    assert bug["owner_id"] is None

    generated_task = client.post(
        "/api/v1/tasks/linked",
        json={
            "source_type": "requirement",
            "source_id": requirement["id"],
            "title": "Generated task has no default owner",
        },
    ).json()
    assert generated_task["owner_id"] is None


def test_project_workflow_scheme_does_not_drive_work_item_current_handlers(client: TestClient):
    db = SessionLocal()
    try:
        users = []
        for username in ["rule_product_api", "rule_developer_api", "rule_tester_api"]:
            user = User(
                username=f"{username}_{uuid4().hex[:6]}",
                full_name=username,
                password_hash=get_password_hash("User123456"),
                is_active=True,
            )
            db.add(user)
            db.flush()
            users.append(user)
        db.commit()
        product_owner_id, developer_id, tester_id = [user.id for user in users]
    finally:
        db.close()

    config = client.post(
        "/api/v1/assignee-rule-configs",
        json={
            "name": f"测试责任人规则-{uuid4().hex[:8]}",
            "requirement_owner_roles": "tester",
            "task_owner_roles": "product_owner",
            "test_case_tester_roles": "developer",
            "test_run_owner_roles": "tester",
            "bug_owner_roles": "product_owner",
        },
    ).json()
    _configure_and_enable_scheme(client, config["id"])
    project = client.post(
        "/api/v1/projects",
        json={"name": f"Rule Defaults Project-{uuid4().hex[:8]}", "assignee_rule_config_id": config["id"]},
    ).json()
    project_id = project["id"]
    assert project["assignee_rule_config_id"] == config["id"]

    saved_members = client.put(
        f"/api/v1/projects/{project_id}/members",
        json=[
            {"user_id": product_owner_id, "project_role": "product_owner", "sort_order": 0},
            {"user_id": developer_id, "project_role": "developer", "sort_order": 1},
            {"user_id": tester_id, "project_role": "tester", "sort_order": 2},
        ],
    )
    assert saved_members.status_code == 200

    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": "Requirement has no current handler from scheme"},
    ).json()
    assert requirement["owner_id"] is None

    standalone_task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "title": "Task has no current handler from scheme"},
    ).json()
    assert standalone_task["owner_id"] is None

    test_case = client.post(
        "/api/v1/test-cases",
        json={"project_id": project_id, "title": "Case uses configured developer"},
    ).json()
    assert test_case["default_tester_id"] == developer_id

    test_run = client.post(
        "/api/v1/test-runs",
        json={"project_id": project_id, "name": "Test run uses configured tester"},
    ).json()
    assert test_run["test_owner_id"] == tester_id

    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "title": "Bug has no current handler from scheme"},
    ).json()
    assert bug["owner_id"] is None

    failed_execution = client.post(
        f"/api/v1/test-cases/{test_case['id']}/executions",
        json={"steps_result_json": [{"step": "submit", "expected": "ok", "result": "failed", "actual": "error"}]},
    )
    assert failed_execution.status_code == 200
    bug_from_case = client.post(
        f"/api/v1/test-cases/{test_case['id']}/bugs",
        json={"title": "Bug from failed case has no current handler from scheme"},
    ).json()
    assert bug_from_case["owner_id"] is None

    generated_task = client.post(
        "/api/v1/tasks/linked",
        json={
            "source_type": "requirement",
            "source_id": requirement["id"],
            "title": "Generated task has no current handler from scheme",
        },
    ).json()
    assert generated_task["owner_id"] is None

    updated = client.patch(f"/api/v1/projects/{project_id}", json={"assignee_rule_config_id": None})
    assert updated.status_code == 200
    assert updated.json()["assignee_rule_config_id"] is None


def test_project_update_records_only_changed_fields(client: TestClient):
    db = SessionLocal()
    try:
        user = User(
            username=f"project.audit.{uuid4().hex[:6]}",
            full_name="Project Auditor",
            password_hash=get_password_hash("User123456"),
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_access_token(user.username)
        actor_id = user.id
    finally:
        db.close()

        project = client.post(
            "/api/v1/projects",
            json={
                "name": f"编辑记录项目-{uuid4().hex[:8]}",
                "description": "原描述",
                "start_date": "2026-07-01",
                "owner_id": actor_id,
            },
        ).json()
    project_id = project["id"]

    updated = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "编辑后项目", "description": "原描述", "start_date": "2026-07-02"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert updated.status_code == 200

    logs = client.get(f"/api/v1/projects/{project_id}/audit-logs")
    assert logs.status_code == 200
    data = logs.json()
    assert len(data) == 1
    assert data[0]["action"] == "update"
    assert data[0]["object_type"] == "project"
    assert data[0]["object_id"] == project_id
    assert data[0]["actor_id"] == actor_id
    assert data[0]["actor_name"] == "Project Auditor"
    assert data[0]["before_data"] == {"name": project["name"], "start_date": "2026-07-01"}
    assert data[0]["after_data"] == {"name": "编辑后项目", "start_date": "2026-07-02"}

    unchanged = client.patch(f"/api/v1/projects/{project_id}", json={"name": "编辑后项目"})
    assert unchanged.status_code == 200
    assert len(client.get(f"/api/v1/projects/{project_id}/audit-logs").json()) == 1


def test_project_can_create_child_project_and_inherit_program(client: TestClient):
    program = client.post("/api/v1/programs", json={"name": f"子项目项目集-{uuid4().hex[:8]}"}).json()
    parent = client.post(
        "/api/v1/projects",
        json={"name": f"父项目-{uuid4().hex[:8]}", "program_id": program["id"]},
    ).json()

    child_response = client.post(
        "/api/v1/projects",
        json={"name": f"子项目-{uuid4().hex[:8]}", "parent_id": parent["id"]},
    )

    assert child_response.status_code == 200
    child = child_response.json()
    assert child["parent_id"] == parent["id"]
    assert child["program_id"] == program["id"]

    invalid = client.patch(f"/api/v1/projects/{parent['id']}", json={"parent_id": parent["id"]})
    assert invalid.status_code == 400
    assert invalid.json()["detail"] == "项目不能选择自身作为上级项目"

    cycle = client.patch(f"/api/v1/projects/{parent['id']}", json={"parent_id": child["id"]})
    assert cycle.status_code == 400
    assert cycle.json()["detail"] == "项目不能选择下级项目作为上级项目"


def test_project_delete_cascades_project_tree_work_items_and_iterations(client: TestClient):
    parent = client.post("/api/v1/projects", json={"name": f"级联删除父项目-{uuid4().hex[:8]}"}).json()
    child = client.post(
        "/api/v1/projects",
        json={"name": f"级联删除子项目-{uuid4().hex[:8]}", "parent_id": parent["id"]},
    ).json()
    iteration = client.post(
        "/api/v1/iterations",
        json={"project_ids": [parent["id"], child["id"]], "name": f"级联删除迭代-{uuid4().hex[:8]}"},
    ).json()
    parent_requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": parent["id"], "iteration_id": iteration["id"], "title": "父项目需求随项目删除"},
    ).json()
    child_requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": child["id"], "iteration_id": iteration["id"], "title": "子项目需求随项目删除"},
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": child["id"], "requirement_id": child_requirement["id"], "title": "子项目任务随项目删除"},
    ).json()
    case = client.post(
        "/api/v1/test-cases",
        json={"project_id": child["id"], "requirement_id": child_requirement["id"], "title": "子项目用例随项目删除"},
    ).json()
    client.post(
        f"/api/v1/test-cases/{case['id']}/executions",
        json={
            "steps_result_json": [
                {"step": "open page", "expected": "page shown", "result": "passed", "actual": "page shown"}
            ]
        },
    )
    test_run = client.post(
        "/api/v1/test-runs",
        json={"project_id": child["id"], "iteration_id": iteration["id"], "name": "子项目测试单随项目删除"},
    ).json()
    selected = client.post(
        f"/api/v1/test-runs/{test_run['id']}/cases",
        json={"test_case_ids": [case["id"]]},
    ).json()
    bug = client.post(
        "/api/v1/bugs",
        json={
            "project_id": child["id"],
            "iteration_id": iteration["id"],
            "requirement_id": child_requirement["id"],
            "task_id": task["id"],
            "test_case_id": case["id"],
            "test_run_id": test_run["id"],
            "title": "子项目Bug随项目删除",
        },
    ).json()

    deleted = client.delete(f"/api/v1/projects/{parent['id']}")

    assert deleted.status_code == 204
    assert client.get(f"/api/v1/projects/{parent['id']}").status_code == 404
    assert client.get(f"/api/v1/projects/{child['id']}").status_code == 404
    assert client.get(f"/api/v1/requirements/{parent_requirement['id']}").status_code == 404
    assert client.get(f"/api/v1/requirements/{child_requirement['id']}").status_code == 404
    assert client.get(f"/api/v1/tasks/{task['id']}").status_code == 404
    assert client.get(f"/api/v1/test-cases/{case['id']}").status_code == 404
    assert client.get(f"/api/v1/bugs/{bug['id']}").status_code == 404
    assert iteration["id"] not in {item["id"] for item in client.get("/api/v1/iterations").json()}
    assert test_run["id"] not in {item["id"] for item in client.get("/api/v1/test-runs").json()}
    assert selected[0]["id"] not in {item["id"] for item in client.get("/api/v1/test-run-cases").json()}
    assert client.get(f"/api/v1/test-cases/{case['id']}/executions").status_code == 404



def test_project_delete_keeps_shared_iteration_and_removes_deleted_project_scope(client: TestClient):
    deleted_project = client.post("/api/v1/projects", json={"name": f"Shared Delete Project-{uuid4().hex[:8]}"}).json()
    kept_project = client.post("/api/v1/projects", json={"name": f"Shared Keep Project-{uuid4().hex[:8]}"}).json()
    iteration = client.post(
        "/api/v1/iterations",
        json={"project_ids": [deleted_project["id"], kept_project["id"]], "name": f"Shared Iteration-{uuid4().hex[:8]}"},
    ).json()
    deleted_requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": deleted_project["id"], "iteration_id": iteration["id"], "title": "Deleted project requirement"},
    ).json()
    kept_requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": kept_project["id"], "iteration_id": iteration["id"], "title": "Kept project requirement"},
    ).json()

    deleted = client.delete(f"/api/v1/projects/{deleted_project['id']}")

    assert deleted.status_code == 204
    listed_iterations = client.get("/api/v1/iterations").json()
    kept_iteration = next(item for item in listed_iterations if item["id"] == iteration["id"])
    assert kept_iteration["project_ids"] == [kept_project["id"]]
    assert client.get(f"/api/v1/requirements/{deleted_requirement['id']}").status_code == 404
    assert client.get(f"/api/v1/requirements/{kept_requirement['id']}").status_code == 200

def test_open_project_move_only_changes_parent(client: TestClient):
    parent = client.post("/api/v1/projects", json={"name": f"父项目-{uuid4().hex[:8]}"}).json()
    project = client.post("/api/v1/projects", json={"name": f"移动项目-{uuid4().hex[:8]}"}).json()
    client.post(f"/api/v1/projects/{project['id']}/start", json={"effective_time": "2026-06-01T09:00:00"})

    moved = client.patch(f"/api/v1/projects/{project['id']}", json={"parent_id": parent["id"]})

    assert moved.status_code == 200
    assert moved.json()["parent_id"] == parent["id"]
    assert moved.json()["status"] == "active"


def test_closed_project_move_only_changes_parent_after_phase_removed(client: TestClient):
    parent = client.post("/api/v1/projects", json={"name": f"最终规则父项目-{uuid4().hex[:8]}"}).json()
    project = client.post("/api/v1/projects", json={"name": f"最终规则子项目-{uuid4().hex[:8]}"}).json()
    development_requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "title": f"转移前需求-{uuid4().hex[:8]}"},
    ).json()
    development_task = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "title": f"转移前任务-{uuid4().hex[:8]}"},
    ).json()
    client.post(f"/api/v1/projects/{project['id']}/start", json={"effective_time": "2026-06-01T09:00:00"})
    blocked_close = client.post(f"/api/v1/projects/{project['id']}/close", json={"effective_time": "2026-06-10T18:00:00"})
    assert blocked_close.status_code == 400

    moved = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={
            "parent_id": parent["id"],
            "maintenance_start_time": "2026-06-11T09:30:00",
            "maintenance_remark": "legacy payload should be ignored",
        },
    )

    assert moved.status_code == 200
    assert moved.json()["parent_id"] == parent["id"]
    assert moved.json()["status"] == "active"
    assert "lifecycle_phase" not in moved.json()
    assert "maintenance_start_time" not in moved.json()
    assert client.get(f"/api/v1/requirements/{development_requirement['id']}").status_code == 200
    assert client.get(f"/api/v1/tasks/{development_task['id']}").status_code == 200

    history = client.get(f"/api/v1/projects/{project['id']}/status-operations").json()
    assert all(item["action"] != "move_to_maintenance" for item in history)


def test_dashboard_summary_reads_database_counts(client: TestClient):
    response = client.get("/api/v1/dashboard/summary")

    assert response.status_code == 200
    data = response.json()
    assert {"programs", "projects", "requirements", "tasks", "open_bugs"} <= set(data)
    assert isinstance(data["projects"], int)


def test_project_requirement_list_filters_by_current_state_id(client: TestClient):
    project = client.post("/api/v1/projects", json={"name": f"状态筛选项目-{uuid4().hex[:8]}"}).json()
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "title": "按节点 ID 筛选的需求"},
    ).json()

    matched = client.get(
        f"/api/v1/projects/{project['id']}/requirements",
        params={"current_state_id": requirement["current_state_id"]},
    )
    unmatched = client.get(
        f"/api/v1/projects/{project['id']}/requirements",
        params={"current_state_id": requirement["current_state_id"] + 999999},
    )

    assert matched.status_code == 200
    assert requirement["id"] in {item["id"] for item in matched.json()["items"]}
    assert unmatched.status_code == 200
    assert requirement["id"] not in {item["id"] for item in unmatched.json()["items"]}


def test_project_close_gate_uses_work_item_state_category(client: TestClient):
    project = client.post("/api/v1/projects", json={"name": f"终态门禁项目-{uuid4().hex[:8]}"}).json()
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "title": "终态门禁需求"},
    ).json()
    db = SessionLocal()
    try:
        stored = db.query(Requirement).filter(Requirement.id == requirement["id"]).first()
        terminal = WorkflowState(
            definition_id=stored.workflow_definition_id,
            status_key=f"test_terminal_{uuid4().hex[:8]}",
            status_name="业务已结束",
            category="terminal",
            enabled=True,
        )
        db.add(terminal)
        db.flush()
        stored.current_state_id = terminal.id
        stored.status = "pending_assignment"
        db.commit()
    finally:
        db.close()

    assert client.post(
        f"/api/v1/projects/{project['id']}/start",
        json={"effective_time": "2026-07-01T09:00:00"},
    ).status_code == 200
    closed = client.post(
        f"/api/v1/projects/{project['id']}/close",
        json={"effective_time": "2026-07-15T18:00:00"},
    )

    assert closed.status_code == 200, closed.text


def test_program_tree_contains_child_programs_and_bound_projects(client: TestClient):
    parent = client.post("/api/v1/programs", json={"name": f"父项目集-{uuid4().hex[:8]}"}).json()
    child = client.post(
        "/api/v1/programs",
        json={"name": f"子项目集-{uuid4().hex[:8]}", "parent_id": parent["id"]},
    ).json()
    project = client.post(
        "/api/v1/projects",
        json={"name": f"绑定项目-{uuid4().hex[:8]}", "program_id": child["id"]},
    ).json()

    response = client.get("/api/v1/programs/tree")

    assert response.status_code == 200
    parent_node = next(item for item in response.json() if item["id"] == parent["id"])
    child_node = next(item for item in parent_node["children"] if item["id"] == child["id"])
    assert any(item["id"] == project["id"] and item["name"] == project["name"] for item in child_node["projects"])


def test_program_tree_contains_unbound_projects_as_top_level_nodes(client: TestClient):
    project = client.post(
        "/api/v1/projects",
        json={"name": f"独立项目-{uuid4().hex[:8]}"},
    ).json()

    response = client.get("/api/v1/programs/tree")

    assert response.status_code == 200
    assert any(
        item["id"] == project["id"] and item["name"] == project["name"] and item.get("node_type") == "project"
        for item in response.json()
    )


def test_project_start_activates_parent_program(client: TestClient):
    parent_program = client.post("/api/v1/programs", json={"name": f"同步父项目集-{uuid4().hex[:8]}"}).json()
    program = client.post(
        "/api/v1/programs",
        json={"name": f"同步项目集-{uuid4().hex[:8]}", "parent_id": parent_program["id"]},
    ).json()
    project = client.post(
        "/api/v1/projects",
        json={"name": f"同步项目-{uuid4().hex[:8]}", "program_id": program["id"]},
    ).json()

    response = client.post(
        f"/api/v1/projects/{project['id']}/start",
        json={"effective_time": "2026-06-01T09:00:00"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "active"
    programs = client.get("/api/v1/programs").json()
    synced_program = next(item for item in programs if item["id"] == program["id"])
    synced_parent_program = next(item for item in programs if item["id"] == parent_program["id"])
    assert synced_program["status"] == "active"
    assert synced_program["actual_start_date"] == "2026-06-01"
    assert synced_parent_program["status"] == "active"
    assert synced_parent_program["actual_start_date"] == "2026-06-01"


def test_project_status_dates_follow_action_rules(client: TestClient):
    project = client.post(
        "/api/v1/projects",
        json={"name": f"项目状态日期-{uuid4().hex[:8]}"},
    ).json()

    missing_start = client.post(f"/api/v1/projects/{project['id']}/start", json={"remark": "no date"})
    assert missing_start.status_code == 400

    started = client.post(
        f"/api/v1/projects/{project['id']}/start",
        json={"effective_time": "2026-06-01T09:00:00", "remark": "start"},
    )
    assert started.status_code == 200
    assert started.json()["actual_start_date"] == "2026-06-01"

    client.post(f"/api/v1/projects/{project['id']}/suspend", json={"remark": "pause"})
    restarted = client.post(f"/api/v1/projects/{project['id']}/start", json={"remark": "resume"})
    assert restarted.status_code == 200
    assert restarted.json()["actual_start_date"] == "2026-06-01"

    missing_close = client.post(f"/api/v1/projects/{project['id']}/close", json={"remark": "no date"})
    assert missing_close.status_code == 400

    closed = client.post(
        f"/api/v1/projects/{project['id']}/close",
        json={"effective_time": "2026-06-08T18:30:00", "remark": "close"},
    )
    assert closed.status_code == 200
    assert closed.json()["actual_end_date"] == "2026-06-08"


def test_project_status_history_uses_authenticated_user_name(client: TestClient):
    db = SessionLocal()
    try:
        user = User(
            username=f"bob.actor.{uuid4().hex[:6]}",
            full_name="Bob",
            password_hash=get_password_hash("User123456"),
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_access_token(user.username)
    finally:
        db.close()

        project = client.post(
            "/api/v1/projects",
            json={"name": f"真实操作人项目-{uuid4().hex[:8]}", "owner_id": user.id},
        ).json()

    started = client.post(
        f"/api/v1/projects/{project['id']}/start",
        json={"effective_time": "2026-06-01T09:00:00"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert started.status_code == 200
    history = client.get(f"/api/v1/projects/{project['id']}/status-operations").json()
    assert history[-1]["action"] == "start"
    assert history[-1]["actor_name"] == "Bob"


def test_program_status_dates_follow_action_rules(client: TestClient):
    program = client.post(
        "/api/v1/programs",
        json={"name": f"项目集状态日期-{uuid4().hex[:8]}"},
    ).json()

    missing_start = client.post(f"/api/v1/programs/{program['id']}/start", json={"remark": "no date"})
    assert missing_start.status_code == 400

    started = client.post(
        f"/api/v1/programs/{program['id']}/start",
        json={"effective_time": "2026-06-02T09:00:00", "remark": "start"},
    )
    assert started.status_code == 200
    assert started.json()["actual_start_date"] == "2026-06-02"

    client.post(f"/api/v1/programs/{program['id']}/suspend", json={"remark": "pause"})
    restarted = client.post(f"/api/v1/programs/{program['id']}/start", json={"remark": "resume"})
    assert restarted.status_code == 200
    assert restarted.json()["actual_start_date"] == "2026-06-02"

    missing_close = client.post(f"/api/v1/programs/{program['id']}/close", json={"remark": "no date"})
    assert missing_close.status_code == 400

    closed = client.post(
        f"/api/v1/programs/{program['id']}/close",
        json={"effective_time": "2026-06-09T18:30:00", "remark": "close"},
    )
    assert closed.status_code == 200
    assert closed.json()["actual_end_date"] == "2026-06-09"


def test_closing_program_blocks_when_descendants_are_not_closed(client: TestClient):
    parent = client.post("/api/v1/programs", json={"name": f"关闭父项目集-{uuid4().hex[:8]}"}).json()
    child = client.post(
        "/api/v1/programs",
        json={"name": f"关闭子项目集-{uuid4().hex[:8]}", "parent_id": parent["id"]},
    ).json()
    client.post(f"/api/v1/programs/{parent['id']}/start", json={"effective_time": "2026-06-01T09:00:00"})

    blocked = client.post(f"/api/v1/programs/{parent['id']}/close")

    assert blocked.status_code == 400
    assert blocked.json()["detail"] == "存在子项目集或项目为未关闭状态"

    client.post(f"/api/v1/programs/{child['id']}/start", json={"effective_time": "2026-06-01T09:00:00"})
    client.post(f"/api/v1/programs/{child['id']}/close", json={"effective_time": "2026-06-02T18:00:00"})
    closed = client.post(f"/api/v1/programs/{parent['id']}/close", json={"effective_time": "2026-06-03T18:00:00"})

    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
