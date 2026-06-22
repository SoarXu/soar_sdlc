from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import SessionLocal


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


def test_project_update_records_only_changed_fields(client: TestClient):
    project = client.post(
        "/api/v1/projects",
        json={
            "name": f"编辑记录项目-{uuid4().hex[:8]}",
            "description": "原描述",
            "start_date": "2026-07-01",
        },
    ).json()
    project_id = project["id"]

    updated = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "编辑后项目", "description": "原描述", "start_date": "2026-07-02"},
    )
    assert updated.status_code == 200

    logs = client.get(f"/api/v1/projects/{project_id}/audit-logs")
    assert logs.status_code == 200
    data = logs.json()
    assert len(data) == 1
    assert data[0]["action"] == "update"
    assert data[0]["object_type"] == "project"
    assert data[0]["object_id"] == project_id
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
    test_run = client.post(
        "/api/v1/test-runs",
        json={"project_id": child["id"], "iteration_id": iteration["id"], "name": "子项目测试单随项目删除"},
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


def test_open_project_move_only_changes_parent(client: TestClient):
    parent = client.post("/api/v1/projects", json={"name": f"父项目-{uuid4().hex[:8]}"}).json()
    project = client.post("/api/v1/projects", json={"name": f"移动项目-{uuid4().hex[:8]}"}).json()
    client.post(f"/api/v1/projects/{project['id']}/start", json={"effective_time": "2026-06-01T09:00:00"})

    moved = client.patch(f"/api/v1/projects/{project['id']}", json={"parent_id": parent["id"]})

    assert moved.status_code == 200
    assert moved.json()["parent_id"] == parent["id"]
    assert moved.json()["status"] == "active"
    assert moved.json()["lifecycle_phase"] == "development"
    assert moved.json()["maintenance_start_time"] is None


def test_closed_project_move_enters_maintenance(client: TestClient):
    parent = client.post("/api/v1/projects", json={"name": f"运维父项目-{uuid4().hex[:8]}"}).json()
    project = client.post("/api/v1/projects", json={"name": f"转运维项目-{uuid4().hex[:8]}"}).json()
    development_requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "title": f"开发需求-{uuid4().hex[:8]}"},
    ).json()
    development_task = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "title": f"开发任务-{uuid4().hex[:8]}"},
    ).json()
    client.post(f"/api/v1/projects/{project['id']}/start", json={"effective_time": "2026-06-01T09:00:00"})
    client.post(f"/api/v1/projects/{project['id']}/close", json={"effective_time": "2026-06-10T18:00:00"})

    moved = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={
            "parent_id": parent["id"],
            "maintenance_start_time": "2026-06-11T09:30:00",
            "maintenance_remark": "关闭后纳入运维项目管理",
        },
    )

    assert moved.status_code == 200
    assert moved.json()["parent_id"] == parent["id"]
    assert moved.json()["status"] == "maintenance"
    assert moved.json()["lifecycle_phase"] == "maintenance"
    assert moved.json()["maintenance_start_time"] == "2026-06-11T09:30:00"
    assert client.get(f"/api/v1/requirements/{development_requirement['id']}").json()["lifecycle_phase"] == "development"
    assert client.get(f"/api/v1/tasks/{development_task['id']}").json()["lifecycle_phase"] == "development"

    maintenance_requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "title": f"运维需求-{uuid4().hex[:8]}"},
    )
    maintenance_task = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "title": f"运维任务-{uuid4().hex[:8]}"},
    )
    assert maintenance_requirement.status_code == 200
    assert maintenance_task.status_code == 200
    assert maintenance_requirement.json()["lifecycle_phase"] == "maintenance"
    assert maintenance_task.json()["lifecycle_phase"] == "maintenance"

    history = client.get(f"/api/v1/projects/{project['id']}/status-operations").json()
    assert any(
        item["action"] == "move_to_maintenance"
        and item["from_status"] == "closed"
        and item["to_status"] == "maintenance"
        and item["remark"] == "关闭后纳入运维项目管理"
        for item in history
    )


def test_dashboard_summary_reads_database_counts(client: TestClient):
    response = client.get("/api/v1/dashboard/summary")

    assert response.status_code == 200
    data = response.json()
    assert {"programs", "projects", "requirements", "tasks", "open_bugs"} <= set(data)
    assert isinstance(data["projects"], int)


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


def test_project_start_activates_parent_program(client: TestClient):
    program = client.post("/api/v1/programs", json={"name": f"同步项目集-{uuid4().hex[:8]}"}).json()
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
    assert synced_program["status"] == "active"


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
