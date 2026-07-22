from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import Base, SessionLocal


def _create_project(client: TestClient) -> int:
    response = client.post("/api/v1/projects", json={"name": f"History Project-{uuid4().hex[:8]}"})
    assert response.status_code == 200
    return response.json()["id"]


def _create_iteration(client: TestClient, project_id: int) -> int:
    response = client.post(
        "/api/v1/iterations",
        json={"project_ids": [project_id], "name": f"History Iteration-{uuid4().hex[:8]}"},
    )
    assert response.status_code == 200
    return response.json()["id"]


def _create_requirement(client: TestClient, project_id: int) -> int:
    response = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"History Requirement-{uuid4().hex[:8]}"},
    )
    assert response.status_code == 200
    return response.json()["id"]


def test_iteration_membership_history_is_registered_in_model_metadata():
    assert "work_item_iteration_history" in Base.metadata.tables


def test_link_and_unlink_requirement_open_and_close_membership_history(client: TestClient):
    project_id = _create_project(client)
    iteration_id = _create_iteration(client, project_id)
    requirement_id = _create_requirement(client, project_id)

    linked = client.post(
        f"/api/v1/iterations/{iteration_id}/requirements",
        json={"requirement_ids": [requirement_id]},
    )
    assert linked.status_code == 200

    db = SessionLocal()
    try:
        row = db.execute(
            text(
                "select iteration_id, enter_reason, left_at from work_item_iteration_history "
                "where object_type = 'requirement' and object_id = :object_id"
            ),
            {"object_id": requirement_id},
        ).one()
        assert row.iteration_id == iteration_id
        assert row.enter_reason == "linked"
        assert row.left_at is None
    finally:
        db.close()

    unlinked = client.delete(f"/api/v1/iterations/{iteration_id}/requirements/{requirement_id}")
    assert unlinked.status_code == 204

    db = SessionLocal()
    try:
        row = db.execute(
            text(
                "select leave_reason, left_at from work_item_iteration_history "
                "where object_type = 'requirement' and object_id = :object_id"
            ),
            {"object_id": requirement_id},
        ).one()
        assert row.leave_reason == "unlinked"
        assert row.left_at is not None
    finally:
        db.close()


def test_requirement_patch_closes_current_membership_history(client: TestClient):
    project_id = _create_project(client)
    iteration_id = _create_iteration(client, project_id)
    response = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
            "title": f"Initially planned requirement-{uuid4().hex[:8]}",
        },
    )
    assert response.status_code == 200
    requirement_id = response.json()["id"]

    updated = client.patch(f"/api/v1/requirements/{requirement_id}", json={"iteration_id": None})
    assert updated.status_code == 200

    db = SessionLocal()
    try:
        row = db.execute(
            text(
                "select enter_reason, leave_reason, left_at from work_item_iteration_history "
                "where object_type = 'requirement' and object_id = :object_id"
            ),
            {"object_id": requirement_id},
        ).one()
        assert row.enter_reason == "created"
        assert row.leave_reason == "updated"
        assert row.left_at is not None
    finally:
        db.close()
