from datetime import datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import Base, SessionLocal
from app.models.requirement import Requirement
from app.models.status_operation import StatusOperationLog
from app.models.work_item_iteration_history import WorkItemIterationHistory
from app.services.work_item_iteration_history_service import move_work_item_to_iteration
from app.db import schema


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
    index_columns = {
        (index.name, tuple(column.name for column in index.columns))
        for index in Base.metadata.tables["work_item_iteration_history"].indexes
    }
    assert ("idx_wiih_object", ("object_type", "object_id", "left_at")) in index_columns


def test_history_open_lookup_schema_recognizes_existing_same_column_index():
    indexes = [{"name": "legacy_open_lookup", "column_names": ["object_type", "object_id", "left_at"]}]

    assert schema._history_open_lookup_index_exists(indexes) is True


def test_history_open_lookup_schema_rejects_same_name_with_wrong_columns():
    indexes = [{"name": "idx_wiih_object", "column_names": ["object_id", "object_type", "left_at"]}]

    assert schema._history_open_lookup_index_exists(indexes) is False


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


def test_iteration_membership_changes_do_not_replace_latest_status_operation(client: TestClient):
    project_id = _create_project(client)
    iteration_id = _create_iteration(client, project_id)
    requirement_id = _create_requirement(client, project_id)
    db = SessionLocal()
    try:
        requirement = db.query(Requirement).filter(Requirement.id == requirement_id).one()
        db.add(StatusOperationLog(
            object_type="requirement",
            object_id=requirement.id,
            action="manual_state_action",
            workflow_definition_id=requirement.workflow_definition_id,
            from_state_id=requirement.current_state_id,
            to_state_id=requirement.current_state_id,
            from_state_name=requirement.status_name,
            to_state_name=requirement.status_name,
            from_status=requirement.status_name,
            to_status=requirement.status_name,
            effective_time=datetime(2026, 7, 1, 9, 0, 0),
            next_owner_id=77,
        ))
        db.commit()
    finally:
        db.close()

    assert client.post(
        f"/api/v1/iterations/{iteration_id}/requirements",
        json={"requirement_ids": [requirement_id]},
    ).status_code == 200
    history = client.get(f"/api/v1/requirements/{requirement_id}/status-operations").json()

    assert [operation["action"] for operation in history] == ["manual_state_action"]
    assert history[-1]["effective_time"].startswith("2026-07-01T09:00:00")
    assert history[-1]["next_owner_id"] == 77


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


def test_membership_move_locks_and_refreshes_stale_work_item_before_history_change(client: TestClient):
    project_id = _create_project(client)
    source_iteration_id = _create_iteration(client, project_id)
    target_iteration_id = _create_iteration(client, project_id)
    created = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "iteration_id": source_iteration_id, "title": f"Concurrent history-{uuid4().hex[:8]}"},
    )
    assert created.status_code == 200
    requirement_id = created.json()["id"]

    stale_db = SessionLocal()
    mover_db = SessionLocal()
    try:
        stale_item = stale_db.query(Requirement).filter(Requirement.id == requirement_id).one()
        moving_requirement = mover_db.query(Requirement).filter(Requirement.id == requirement_id).one()
        move_work_item_to_iteration(
            mover_db,
            moving_requirement,
            target_iteration_id,
            actor_id=1,
            reason="first_move",
        )
        mover_db.commit()
        first_target_history_id = mover_db.query(WorkItemIterationHistory.id).filter(
            WorkItemIterationHistory.object_type == "requirement",
            WorkItemIterationHistory.object_id == requirement_id,
            WorkItemIterationHistory.iteration_id == target_iteration_id,
        ).scalar()

        assert stale_item.iteration_id == source_iteration_id
        move_work_item_to_iteration(
            stale_db,
            stale_item,
            target_iteration_id,
            actor_id=1,
            reason="stale_duplicate_move",
        )
        stale_db.commit()

        open_target_rows = stale_db.query(WorkItemIterationHistory).filter(
            WorkItemIterationHistory.object_type == "requirement",
            WorkItemIterationHistory.object_id == requirement_id,
            WorkItemIterationHistory.iteration_id == target_iteration_id,
            WorkItemIterationHistory.left_at.is_(None),
        ).all()
        assert len(open_target_rows) == 1
        all_target_rows = stale_db.query(WorkItemIterationHistory).filter(
            WorkItemIterationHistory.object_type == "requirement",
            WorkItemIterationHistory.object_id == requirement_id,
            WorkItemIterationHistory.iteration_id == target_iteration_id,
        ).all()
        assert [row.id for row in all_target_rows] == [first_target_history_id]
    finally:
        stale_db.close()
        mover_db.close()
