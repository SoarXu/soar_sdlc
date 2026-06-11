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

    started = client.post(f"/api/v1/programs/{program_id}/start")
    assert started.status_code == 200
    assert started.json()["status"] == "active"

    suspended = client.post(f"/api/v1/programs/{program_id}/suspend")
    assert suspended.status_code == 200
    assert suspended.json()["status"] == "paused"

    restarted = client.post(
        f"/api/v1/programs/{program_id}/start",
        json={"effective_time": "2026-06-10T11:31:59", "remark": "重新启动项目集"},
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

    started = client.post(f"/api/v1/projects/{project_id}/start")
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

    closed = client.post(f"/api/v1/projects/{project_id}/close")
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


def test_open_project_move_only_changes_parent(client: TestClient):
    parent = client.post("/api/v1/projects", json={"name": f"父项目-{uuid4().hex[:8]}"}).json()
    project = client.post("/api/v1/projects", json={"name": f"移动项目-{uuid4().hex[:8]}"}).json()
    client.post(f"/api/v1/projects/{project['id']}/start")

    moved = client.patch(f"/api/v1/projects/{project['id']}", json={"parent_id": parent["id"]})

    assert moved.status_code == 200
    assert moved.json()["parent_id"] == parent["id"]
    assert moved.json()["status"] == "active"
    assert moved.json()["lifecycle_phase"] == "development"
    assert moved.json()["maintenance_start_time"] is None


def test_closed_project_move_enters_maintenance(client: TestClient):
    parent = client.post("/api/v1/projects", json={"name": f"运维父项目-{uuid4().hex[:8]}"}).json()
    project = client.post("/api/v1/projects", json={"name": f"转运维项目-{uuid4().hex[:8]}"}).json()
    client.post(f"/api/v1/projects/{project['id']}/start")
    client.post(f"/api/v1/projects/{project['id']}/close")

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

    response = client.post(f"/api/v1/projects/{project['id']}/start")

    assert response.status_code == 200
    assert response.json()["status"] == "active"
    programs = client.get("/api/v1/programs").json()
    synced_program = next(item for item in programs if item["id"] == program["id"])
    assert synced_program["status"] == "active"


def test_closing_program_blocks_when_descendants_are_not_closed(client: TestClient):
    parent = client.post("/api/v1/programs", json={"name": f"关闭父项目集-{uuid4().hex[:8]}"}).json()
    child = client.post(
        "/api/v1/programs",
        json={"name": f"关闭子项目集-{uuid4().hex[:8]}", "parent_id": parent["id"]},
    ).json()
    client.post(f"/api/v1/programs/{parent['id']}/start")

    blocked = client.post(f"/api/v1/programs/{parent['id']}/close")

    assert blocked.status_code == 400
    assert blocked.json()["detail"] == "存在子项目集或项目为未关闭状态"

    client.post(f"/api/v1/programs/{child['id']}/start")
    client.post(f"/api/v1/programs/{child['id']}/close")
    closed = client.post(f"/api/v1/programs/{parent['id']}/close")

    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
