from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import SessionLocal


def test_program_crud_persists_to_database(client: TestClient):
    name = f"项目集-{uuid4().hex[:8]}"

    created = client.post(
        "/api/v1/programs",
        json={"name": name, "department": "研发中心", "status": "active", "description": "API 创建"},
    )
    assert created.status_code == 200
    program_id = created.json()["id"]

    db = SessionLocal()
    try:
        stored_name = db.execute(text("select name from programs where id = :id"), {"id": program_id}).scalar_one()
        assert stored_name == name
    finally:
        db.close()

    updated = client.patch(f"/api/v1/programs/{program_id}", json={"status": "closed"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "closed"

    deleted = client.delete(f"/api/v1/programs/{program_id}")
    assert deleted.status_code == 204

    listed = client.get("/api/v1/programs")
    assert all(item["id"] != program_id for item in listed.json())


def test_project_crud_uses_prd_fields(client: TestClient):
    name = f"项目-{uuid4().hex[:8]}"

    created = client.post(
        "/api/v1/projects",
        json={"name": name, "status": "active", "description": "项目 API 创建"},
    )
    assert created.status_code == 200
    project_id = created.json()["id"]
    assert created.json()["name"] == name
    assert "owner_id" in created.json()

    updated = client.patch(f"/api/v1/projects/{project_id}", json={"description": "已更新"})
    assert updated.status_code == 200
    assert updated.json()["description"] == "已更新"

    deleted = client.delete(f"/api/v1/projects/{project_id}")
    assert deleted.status_code == 204


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
