from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.jobs.iteration_jobs import run_auto_start_due_iterations
from app.models.requirement import Requirement
from app.models.task import Task


def _create_project(client: TestClient, name: str | None = None, parent_id: int | None = None) -> int:
    payload = {"name": name or f"Project-{uuid4().hex[:8]}"}
    if parent_id:
        payload["parent_id"] = parent_id
    response = client.post("/api/v1/projects", json=payload)
    assert response.status_code == 200
    return response.json()["id"]


def _create_iteration(client: TestClient, project_ids: list[int], name: str | None = None, status: str = "planning") -> int:
    response = client.post(
        "/api/v1/iterations",
        json={"project_ids": project_ids, "name": name or f"Iteration-{uuid4().hex[:8]}", "status": status},
    )
    assert response.status_code == 200
    return response.json()["id"]


def _create_requirement(client: TestClient, project_id: int, title: str | None = None, owner_id: int | None = None) -> int:
    response = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": title or f"Requirement-{uuid4().hex[:8]}", "owner_id": owner_id},
    )
    assert response.status_code == 200
    return response.json()["id"]


def _create_task(
    client: TestClient,
    project_id: int,
    title: str | None = None,
    requirement_id: int | None = None,
    owner_id: int | None = None,
) -> int:
    payload = {"project_id": project_id, "title": title or f"Task-{uuid4().hex[:8]}", "owner_id": owner_id}
    if requirement_id:
        payload["requirement_id"] = requirement_id
    response = client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 200
    return response.json()["id"]


def _create_case(client: TestClient, project_id: int, requirement_id: int, title: str | None = None) -> int:
    response = client.post(
        "/api/v1/test-cases",
        json={"project_id": project_id, "requirement_id": requirement_id, "title": title or f"Case-{uuid4().hex[:8]}"},
    )
    assert response.status_code == 200
    return response.json()["id"]


def _create_bug(client: TestClient, project_id: int, iteration_id: int, title: str | None = None, owner_id: int | None = None) -> int:
    response = client.post(
        "/api/v1/bugs",
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
            "title": title or f"Bug-{uuid4().hex[:8]}",
            "owner_id": owner_id,
        },
    )
    assert response.status_code == 200
    return response.json()["id"]


def _set_requirement_status(requirement_id: int, status: str) -> None:
    db = SessionLocal()
    try:
        db.query(Requirement).filter(Requirement.id == requirement_id).update({"status": status})
        db.commit()
    finally:
        db.close()


def _set_task_status(task_id: int, status: str) -> None:
    db = SessionLocal()
    try:
        db.query(Task).filter(Task.id == task_id).update({"status": status})
        db.commit()
    finally:
        db.close()


def test_iteration_crud_persists_to_database(client: TestClient):
    project_id = _create_project(client)

    created = client.post(
        "/api/v1/iterations",
        json={"project_id": project_id, "name": "MVP 迭代", "status": "planning", "goal": "完成主链路"},
    )
    assert created.status_code == 200
    iteration_id = created.json()["id"]
    assert created.json()["project_id"] == project_id

    updated = client.patch(f"/api/v1/iterations/{iteration_id}", json={"status": "active"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "active"

    deleted = client.delete(f"/api/v1/iterations/{iteration_id}")
    assert deleted.status_code == 204


def test_iteration_detail_collects_scoped_projects_and_linked_objects(client: TestClient):
    root_project = _create_project(client, "Root project")
    child_project = _create_project(client, "Child project", parent_id=root_project)
    other_project = _create_project(client, "Other project")
    iteration_id = _create_iteration(client, [root_project], "Scoped iteration")

    root_requirement = _create_requirement(client, root_project, "Root requirement")
    child_requirement = _create_requirement(client, child_project, "Child requirement")
    other_requirement = _create_requirement(client, other_project, "Other requirement")
    root_task = _create_task(client, root_project, "Root task", requirement_id=root_requirement)
    child_task = _create_task(client, child_project, "Child task")
    _create_task(client, other_project, "Other task")
    _create_case(client, child_project, child_requirement, "Child case")
    _create_bug(client, root_project, iteration_id, "Root bug")

    linked_requirements = client.post(
        f"/api/v1/iterations/{iteration_id}/requirements",
        json={"requirement_ids": [root_requirement, child_requirement]},
    )
    linked_tasks = client.post(
        f"/api/v1/iterations/{iteration_id}/tasks",
        json={"task_ids": [child_task]},
    )
    assert linked_requirements.status_code == 200
    assert linked_tasks.status_code == 200

    detail = client.get(f"/api/v1/iterations/{iteration_id}/detail")
    assert detail.status_code == 200
    requirement_ids = {item["id"] for item in detail.json()["requirements"]}
    task_ids = {item["id"] for item in detail.json()["tasks"]}
    project_names = {
        detail.json()["projects"][0]["name"],
        *[child["name"] for child in detail.json()["projects"][0]["children"]],
    }

    assert root_requirement in requirement_ids
    assert child_requirement in requirement_ids
    assert other_requirement not in requirement_ids
    assert root_task in task_ids
    assert child_task in task_ids
    assert project_names == {"Root project", "Child project"}


def test_iteration_job_auto_starts_without_changing_child_item_statuses(client: TestClient):
    project_id = _create_project(client)
    iteration_id = _create_iteration(client, [project_id], "Auto start iteration", status="planning")
    update = client.patch(f"/api/v1/iterations/{iteration_id}", json={"start_date": "2026-06-01"})
    assert update.status_code == 200

    requirement_id = _create_requirement(client, project_id, "Auto start requirement")
    task_id = _create_task(client, project_id, "Auto start task")
    assert client.post(f"/api/v1/iterations/{iteration_id}/requirements", json={"requirement_ids": [requirement_id]}).status_code == 200
    assert client.post(f"/api/v1/iterations/{iteration_id}/tasks", json={"task_ids": [task_id]}).status_code == 200

    started_count = run_auto_start_due_iterations()
    detail = client.get(f"/api/v1/iterations/{iteration_id}/detail")

    assert started_count == 1
    assert detail.status_code == 200
    assert detail.json()["iteration"]["status"] == "active"
    assert detail.json()["iteration"]["actual_start_date"] == "2026-06-01"
    assert client.get(f"/api/v1/requirements/{requirement_id}").json()["status"] == "pending_assignment"
    assert client.get(f"/api/v1/tasks/{task_id}").json()["status"] == "pending_assignment"


def test_iteration_start_keeps_child_work_items_on_their_own_workflows(client: TestClient):
    project_id = _create_project(client)
    iteration_id = _create_iteration(client, [project_id])
    requirement_id = _create_requirement(client, project_id, "Requirement for iteration start")
    canceled_requirement_id = _create_requirement(client, project_id, "Canceled requirement")
    canceled_requirement = client.post(
        f"/api/v1/requirements/{canceled_requirement_id}/close",
        json={"reason": "done", "remark": "canceled before iteration start"},
    )
    assert canceled_requirement.status_code == 200

    requirement_task_id = _create_task(client, project_id, "Task under requirement", requirement_id=requirement_id)
    standalone_task_id = _create_task(client, project_id, "Standalone task linked to iteration")
    canceled_task_id = _create_task(client, project_id, "Canceled task")
    canceled_task = client.post(
        f"/api/v1/tasks/{canceled_task_id}/close",
        json={"reason": "done", "remark": "canceled before iteration start"},
    )
    assert canceled_task.status_code == 200

    assert client.post(
        f"/api/v1/iterations/{iteration_id}/requirements",
        json={"requirement_ids": [requirement_id, canceled_requirement_id]},
    ).status_code == 200
    assert client.post(
        f"/api/v1/iterations/{iteration_id}/tasks",
        json={"task_ids": [standalone_task_id, canceled_task_id]},
    ).status_code == 200

    started = client.post(
        f"/api/v1/iterations/{iteration_id}/start",
        json={"effective_time": "2026-06-12T09:30:00", "remark": "iteration kickoff"},
    )

    assert started.status_code == 200
    assert client.get(f"/api/v1/requirements/{requirement_id}").json()["status"] == "pending_assignment"
    assert client.get(f"/api/v1/requirements/{canceled_requirement_id}").json()["status"] == "canceled"
    assert client.get(f"/api/v1/tasks/{requirement_task_id}").json()["status"] == "pending_assignment"
    assert client.get(f"/api/v1/tasks/{standalone_task_id}").json()["status"] == "pending_assignment"
    assert client.get(f"/api/v1/tasks/{canceled_task_id}").json()["status"] == "canceled"


def test_iteration_finish_is_blocked_by_unfinished_direct_items(client: TestClient):
    project_id = _create_project(client)
    iteration_id = _create_iteration(client, [project_id], status="active")
    requirement_id = _create_requirement(client, project_id, "Open requirement")
    task_id = _create_task(client, project_id, "Open task")
    _create_bug(client, project_id, iteration_id, "Open bug")
    assert client.post(f"/api/v1/iterations/{iteration_id}/requirements", json={"requirement_ids": [requirement_id]}).status_code == 200
    assert client.post(f"/api/v1/iterations/{iteration_id}/tasks", json={"task_ids": [task_id]}).status_code == 200

    finished = client.post(
        f"/api/v1/iterations/{iteration_id}/finish",
        json={"effective_time": "2026-06-10T18:00:00"},
    )

    assert finished.status_code == 400
    assert client.get(f"/api/v1/iterations/{iteration_id}/detail").json()["iteration"]["status"] == "active"


def test_iteration_defer_moves_selected_unfinished_items(client: TestClient):
    project_id = _create_project(client)
    current_iteration_id = _create_iteration(client, [project_id], "Current iteration", status="active")
    target_iteration_id = _create_iteration(client, [project_id], "Target iteration", status="planning")
    requirement_id = _create_requirement(client, project_id, "Deferred requirement")
    task_id = _create_task(client, project_id, "Deferred task")
    assert client.post(f"/api/v1/iterations/{current_iteration_id}/requirements", json={"requirement_ids": [requirement_id]}).status_code == 200
    assert client.post(f"/api/v1/iterations/{current_iteration_id}/tasks", json={"task_ids": [task_id]}).status_code == 200
    _set_requirement_status(requirement_id, "in_processing")
    _set_task_status(task_id, "in_processing")

    deferred = client.post(
        f"/api/v1/iterations/{current_iteration_id}/defer-work-items",
        json={"target_iteration_id": target_iteration_id, "requirement_ids": [requirement_id], "task_ids": [task_id]},
    )

    assert deferred.status_code == 200
    assert deferred.json()["moved_requirement_ids"] == [requirement_id]
    assert deferred.json()["moved_task_ids"] == [task_id]
    assert client.get(f"/api/v1/iterations/{target_iteration_id}/detail").status_code == 200
