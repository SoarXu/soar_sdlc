from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.models.task import Task
from app.models.workflow_definition import WorkflowState
from app.services.default_workflow_template_service import graph_for_object_type


def _create_project(client: TestClient) -> int:
    response = client.post("/api/v1/projects", json={"name": f"Task terminal gate {uuid4().hex[:8]}"})
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _create_task_tree(client: TestClient, *, task_type: str = "standalone_operation") -> tuple[dict, dict, dict]:
    project_id = _create_project(client)
    root = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "title": "Root task", "task_type": task_type},
    )
    assert root.status_code == 200, root.text
    root = root.json()
    with SessionLocal() as db:
        parent = db.query(Task).filter(Task.id == root["id"]).one()
        child = Task(
            project_id=parent.project_id,
            iteration_id=parent.iteration_id,
            requirement_id=parent.requirement_id,
            parent_task_id=parent.id,
            title="Child task",
            task_type="standalone_operation",
            priority="medium",
            workflow_definition_id=parent.workflow_definition_id,
            current_state_id=parent.current_state_id,
            lifecycle_phase=parent.lifecycle_phase,
            creator_id=parent.creator_id,
        )
        db.add(child)
        db.flush()
        grandchild = Task(
            project_id=child.project_id,
            iteration_id=child.iteration_id,
            requirement_id=child.requirement_id,
            parent_task_id=child.id,
            title="Grandchild task",
            task_type="standalone_operation",
            priority="medium",
            workflow_definition_id=child.workflow_definition_id,
            current_state_id=child.current_state_id,
            lifecycle_phase=child.lifecycle_phase,
            creator_id=child.creator_id,
        )
        db.add(grandchild)
        db.commit()
        db.refresh(child)
        db.refresh(grandchild)
        return root, _task_read(child), _task_read(grandchild)


def _task_read(task: Task) -> dict:
    return {"id": task.id, "title": task.title, "status_name": task.status_name}


def _set_task_state(task_id: int, *, state_role: str | None = None, terminal_kind: str | None = None, owner: bool = False) -> None:
    assert state_role or terminal_kind
    with SessionLocal() as db:
        task = db.query(Task).filter(Task.id == task_id).one()
        state = (
            db.query(WorkflowState)
            .filter(
                WorkflowState.definition_id == task.workflow_definition_id,
                WorkflowState.state_role == state_role if state_role else WorkflowState.terminal_kind == terminal_kind,
            )
            .one()
        )
        task.current_state_id = state.id
        if owner:
            task.owner_id = task.creator_id
        db.commit()


@pytest.mark.parametrize(
    ("action_key", "root_state_role"),
    [("complete", "active_work"), ("cancel", "unassigned")],
)
def test_task_terminal_transitions_block_all_open_descendants(
    client: TestClient, action_key: str, root_state_role: str
):
    root, child, grandchild = _create_task_tree(client)
    _set_task_state(root["id"], state_role=root_state_role, owner=action_key == "complete")

    response = client.post(
        f"/api/v1/workflow-runtime/task/{root['id']}/transition",
        json={"action_key": action_key},
    )

    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "TASK_DESCENDANTS_NOT_TERMINAL"
    assert detail["counts"] == {"task": 2}
    assert detail["blockers"] == [
        {
            "id": child["id"],
            "title": child["title"],
            "status_name": child["status_name"],
            "parent_task_id": root["id"],
        },
        {
            "id": grandchild["id"],
            "title": grandchild["title"],
            "status_name": grandchild["status_name"],
            "parent_task_id": child["id"],
        },
    ]


def test_task_confirmation_completion_blocks_open_descendants_only_when_entering_terminal_state(client: TestClient):
    root, _child, _grandchild = _create_task_tree(client, task_type="bug_fix")
    _set_task_state(root["id"], state_role="active_work", owner=True)

    submitted = client.post(
        f"/api/v1/workflow-runtime/task/{root['id']}/transition",
        json={"action_key": "submit_confirmation"},
    )

    assert submitted.status_code == 200, submitted.text
    blocked = client.post(
        f"/api/v1/workflow-runtime/task/{root['id']}/transition",
        json={"action_key": "approve_confirmation"},
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["detail"]["code"] == "TASK_DESCENDANTS_NOT_TERMINAL"


def test_task_terminal_transition_allows_terminal_descendants(client: TestClient):
    root, child, grandchild = _create_task_tree(client)
    _set_task_state(child["id"], terminal_kind="completed")
    _set_task_state(grandchild["id"], terminal_kind="terminated")

    completed = client.post(
        f"/api/v1/workflow-runtime/task/{root['id']}/transition",
        json={"action_key": "cancel"},
    )
    assert completed.status_code == 200, completed.text


def test_task_terminal_transition_ignores_deleted_descendants(client: TestClient):
    root, deleted_child, _ = _create_task_tree(client)
    with SessionLocal() as db:
        db.query(Task).filter(Task.id == deleted_child["id"]).update({Task.deleted: 1})
        db.commit()
    deleted_ignored = client.post(
        f"/api/v1/workflow-runtime/task/{root['id']}/transition",
        json={"action_key": "cancel"},
    )
    assert deleted_ignored.status_code == 200, deleted_ignored.text


def test_default_task_terminal_transitions_declare_the_descendant_gate():
    graph = graph_for_object_type("task")
    terminal_refs = {state.ref for state in graph.states if state.category == "terminal"}
    terminal_transitions = [
        transition
        for transition in graph.transitions
        if transition.to_ref in terminal_refs and transition.from_ref != transition.to_ref
    ]

    assert terminal_transitions
    assert all(
        (transition.validator_config or {}).get("type") == "task_descendants_terminal_gate"
        for transition in terminal_transitions
    )
