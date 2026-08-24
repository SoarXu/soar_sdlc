from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.models.project_member import ProjectMember
from app.models.role import RoleCapability
from app.models.workflow_definition import WorkflowState


def _create_project_with_iterations(client: TestClient) -> tuple[dict, int, int]:
    project = client.post(
        "/api/v1/projects",
        json={"name": f"State matrix project {uuid4().hex[:8]}"},
    )
    assert project.status_code == 200, project.text
    project_data = project.json()
    _add_project_owner_member(project_data["id"], project_data["owner_id"])
    planned = client.post(
        "/api/v1/iterations",
        json={"project_ids": [project_data["id"]], "name": f"Planned {uuid4().hex[:8]}"},
    )
    assert planned.status_code == 200, planned.text
    active = client.post(
        "/api/v1/iterations",
        json={"project_ids": [project_data["id"]], "name": f"Active {uuid4().hex[:8]}"},
    )
    assert active.status_code == 200, active.text
    started = client.post(
        f"/api/v1/workflow-runtime/iteration/{active.json()['id']}/transition",
        json={"action_key": "start"},
    )
    assert started.status_code == 200, started.text
    return project_data, planned.json()["id"], active.json()["id"]


def _add_project_owner_member(project_id: int, user_id: int) -> None:
    with SessionLocal() as db:
        role_id = db.query(RoleCapability.role_id).filter(RoleCapability.capability == "project_owner").scalar()
        assert role_id is not None
        if not db.query(ProjectMember.id).filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
            ProjectMember.role_id == role_id,
        ).first():
            db.add(ProjectMember(project_id=project_id, user_id=user_id, role_id=role_id))
            db.commit()


def _create_work_item(client: TestClient, object_type: str, project_id: int, iteration_id: int, owner_id: int | None) -> dict:
    payload = {
        "project_id": project_id,
        "iteration_id": iteration_id,
        "title": f"{object_type} state matrix {uuid4().hex[:8]}",
        "owner_id": owner_id,
    }
    response = client.post(f"/api/v1/{object_type}s", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def _state_role(item: dict) -> str | None:
    with SessionLocal() as db:
        return db.query(WorkflowState.state_role).filter(WorkflowState.id == item["current_state_id"]).scalar()


@pytest.mark.parametrize("object_type", ["requirement", "task", "bug"])
def test_creation_state_role_follows_owner_and_iteration_phase(client: TestClient, object_type: str):
    project, planned_iteration_id, active_iteration_id = _create_project_with_iterations(client)
    owner_id = project["owner_id"]

    assert _state_role(_create_work_item(client, object_type, project["id"], planned_iteration_id, None)) == "unassigned"
    assert _state_role(_create_work_item(client, object_type, project["id"], planned_iteration_id, owner_id)) == "waiting_iteration"
    assert _state_role(_create_work_item(client, object_type, project["id"], active_iteration_id, None)) == "unassigned"
    assert _state_role(_create_work_item(client, object_type, project["id"], active_iteration_id, owner_id)) == "active_work"


@pytest.mark.parametrize("object_type", ["requirement", "task", "bug"])
def test_assignment_and_unassignment_follow_iteration_phase(client: TestClient, object_type: str):
    project, planned_iteration_id, active_iteration_id = _create_project_with_iterations(client)
    owner_id = project["owner_id"]

    planned_item = _create_work_item(client, object_type, project["id"], planned_iteration_id, None)
    planned_assignment = client.post(
        f"/api/v1/workflow-runtime/{object_type}/{planned_item['id']}/transition",
        json={"action_key": "assign", "next_owner_id": owner_id},
    )
    assert planned_assignment.status_code == 200, planned_assignment.text
    assert planned_assignment.json()["owner_id"] == owner_id
    assert _state_role(planned_assignment.json()) == "waiting_iteration"

    unassigned = client.post(
        f"/api/v1/workflow-runtime/{object_type}/{planned_item['id']}/transition",
        json={"action_key": "unassign"},
    )
    assert unassigned.status_code == 200, unassigned.text
    assert unassigned.json()["owner_id"] is None
    assert _state_role(unassigned.json()) == "unassigned"

    active_item = _create_work_item(client, object_type, project["id"], active_iteration_id, None)
    active_assignment = client.post(
        f"/api/v1/workflow-runtime/{object_type}/{active_item['id']}/transition",
        json={"action_key": "assign", "next_owner_id": owner_id},
    )
    assert active_assignment.status_code == 200, active_assignment.text
    assert active_assignment.json()["owner_id"] == owner_id
    assert _state_role(active_assignment.json()) == "active_work"


@pytest.mark.parametrize("object_type", ["requirement", "task", "bug"])
def test_iteration_start_activates_waiting_items_and_records_history(client: TestClient, object_type: str):
    project, planned_iteration_id, _active_iteration_id = _create_project_with_iterations(client)
    waiting_item = _create_work_item(
        client,
        object_type,
        project["id"],
        planned_iteration_id,
        project["owner_id"],
    )
    unassigned_item = _create_work_item(client, object_type, project["id"], planned_iteration_id, None)
    assert _state_role(waiting_item) == "waiting_iteration"
    assert _state_role(unassigned_item) == "unassigned"

    started = client.post(
        f"/api/v1/workflow-runtime/iteration/{planned_iteration_id}/transition",
        json={"action_key": "start"},
    )
    assert started.status_code == 200, started.text

    waiting_detail = client.get(f"/api/v1/{object_type}s/{waiting_item['id']}")
    unassigned_detail = client.get(f"/api/v1/{object_type}s/{unassigned_item['id']}")
    assert waiting_detail.status_code == 200
    assert unassigned_detail.status_code == 200
    assert _state_role(waiting_detail.json()) == "active_work"
    assert _state_role(unassigned_detail.json()) == "unassigned"
    history = client.get(f"/api/v1/{object_type}s/{waiting_item['id']}/status-operations")
    assert history.status_code == 200
    assert any(item["action"] == "start_iteration" for item in history.json())


@pytest.mark.parametrize("object_type", ["requirement", "task", "bug"])
def test_iteration_move_activates_waiting_items_and_blocks_active_work_regression(client: TestClient, object_type: str):
    project, planned_iteration_id, active_iteration_id = _create_project_with_iterations(client)
    waiting_item = _create_work_item(
        client,
        object_type,
        project["id"],
        planned_iteration_id,
        project["owner_id"],
    )
    moved = client.patch(
        f"/api/v1/{object_type}s/{waiting_item['id']}",
        json={"iteration_id": active_iteration_id},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["iteration_id"] == active_iteration_id
    assert _state_role(moved.json()) == "active_work"
    history = client.get(f"/api/v1/{object_type}s/{waiting_item['id']}/status-operations")
    assert any(item["action"] == "start_iteration" for item in history.json())

    active_item = _create_work_item(
        client,
        object_type,
        project["id"],
        active_iteration_id,
        project["owner_id"],
    )
    blocked = client.patch(
        f"/api/v1/{object_type}s/{active_item['id']}",
        json={"iteration_id": planned_iteration_id},
    )
    assert blocked.status_code == 409
    after_block = client.get(f"/api/v1/{object_type}s/{active_item['id']}")
    assert after_block.status_code == 200
    assert after_block.json()["iteration_id"] == active_iteration_id
    assert _state_role(after_block.json()) == "active_work"
