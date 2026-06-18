from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.models.user import User


def _create_project(client: TestClient, name: str | None = None, parent_id: int | None = None) -> int:
    payload = {"name": name or f"Project-{uuid4().hex[:8]}"}
    if parent_id:
        payload["parent_id"] = parent_id
    response = client.post("/api/v1/projects", json=payload)
    assert response.status_code == 200
    return response.json()["id"]


def _create_user(client: TestClient, username: str | None = None, full_name: str | None = None) -> int:
    suffix = uuid4().hex[:8]
    db = SessionLocal()
    try:
        user = User(
            username=username or f"user_{suffix}",
            full_name=full_name or f"User {suffix}",
            password_hash="test",
            department="QA",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id
    finally:
        db.close()


def _create_iteration(client: TestClient, project_ids: list[int], name: str | None = None) -> int:
    response = client.post(
        "/api/v1/iterations",
        json={"project_ids": project_ids, "name": name or f"Iteration-{uuid4().hex[:8]}", "status": "planning"},
    )
    assert response.status_code == 200
    return response.json()["id"]


def _create_requirement(client: TestClient, project_id: int, title: str | None = None, status: str = "draft") -> int:
    response = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": title or f"Requirement-{uuid4().hex[:8]}", "status": status},
    )
    assert response.status_code == 200
    requirement_id = response.json()["id"]
    if status == "closed":
        close_response = client.post(
            f"/api/v1/requirements/{requirement_id}/close",
            json={"reason": "done", "remark": "closed for iteration metric"},
        )
        assert close_response.status_code == 200
    return requirement_id


def _create_task(
    client: TestClient,
    project_id: int,
    title: str | None = None,
    requirement_id: int | None = None,
) -> int:
    payload = {"project_id": project_id, "title": title or f"Task-{uuid4().hex[:8]}", "status": "todo"}
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


def test_iteration_detail_links_requirements_tasks_and_metrics(client: TestClient):
    root_project = _create_project(client, "Root Project")
    child_project = _create_project(client, "Child Project", parent_id=root_project)
    other_project = _create_project(client, "Other Project")
    iteration_id = _create_iteration(client, [root_project])

    root_req = _create_requirement(client, root_project, "Root requirement", status="closed")
    child_req = _create_requirement(client, child_project, "Child requirement")
    other_req = _create_requirement(client, other_project, "Other requirement")
    root_task = _create_task(client, root_project, "Root task", requirement_id=root_req)
    child_task = _create_task(client, child_project, "Child standalone task")
    other_task = _create_task(client, other_project, "Other task")
    case_id = _create_case(client, root_project, root_req, "Root case")

    available_requirements = client.get(f"/api/v1/iterations/{iteration_id}/available-requirements")
    assert available_requirements.status_code == 200
    assert {item["id"] for item in available_requirements.json()} == {root_req, child_req}
    assert other_req not in {item["id"] for item in available_requirements.json()}

    linked_requirements = client.post(
        f"/api/v1/iterations/{iteration_id}/requirements",
        json={"requirement_ids": [root_req, child_req]},
    )
    assert linked_requirements.status_code == 200

    available_tasks = client.get(f"/api/v1/iterations/{iteration_id}/available-tasks")
    assert available_tasks.status_code == 200
    assert {item["id"] for item in available_tasks.json()} == {child_task}
    assert other_task not in {item["id"] for item in available_tasks.json()}

    linked_tasks = client.post(f"/api/v1/iterations/{iteration_id}/tasks", json={"task_ids": [child_task]})
    assert linked_tasks.status_code == 200

    detail = client.get(f"/api/v1/iterations/{iteration_id}/detail")
    assert detail.status_code == 200
    data = detail.json()
    assert {item["id"] for item in data["requirements"]} == {root_req, child_req}
    assert {item["id"] for item in data["tasks"]} == {root_task, child_task}
    assert {item["id"] for item in data["test_cases"]} == {case_id}
    assert "owner_id" in data["projects"][0]
    assert data["metrics"]["requirement_total"] == 2
    assert data["metrics"]["closed_requirement_total"] == 1
    assert data["metrics"]["progress_rate"] == 0.5
    assert data["metrics"]["covered_requirement_total"] == 1
    assert data["metrics"]["test_coverage_rate"] == 0.5

    second_iteration_id = _create_iteration(client, [root_project], "Second iteration")
    unavailable = client.get(f"/api/v1/iterations/{second_iteration_id}/available-requirements")
    assert unavailable.status_code == 200
    assert root_req not in {item["id"] for item in unavailable.json()}
    assert child_req not in {item["id"] for item in unavailable.json()}

    removed_requirement = client.delete(f"/api/v1/iterations/{iteration_id}/requirements/{root_req}")
    assert removed_requirement.status_code == 204
    detail_after_requirement_remove = client.get(f"/api/v1/iterations/{iteration_id}/detail").json()
    assert root_req not in {item["id"] for item in detail_after_requirement_remove["requirements"]}
    assert root_task not in {item["id"] for item in detail_after_requirement_remove["tasks"]}

    removed_task = client.delete(f"/api/v1/iterations/{iteration_id}/tasks/{child_task}")
    assert removed_task.status_code == 204
    detail_after_task_remove = client.get(f"/api/v1/iterations/{iteration_id}/detail").json()
    assert child_task not in {item["id"] for item in detail_after_task_remove["tasks"]}


def test_generated_task_for_linked_requirement_appears_in_iteration_detail(client: TestClient):
    project_id = _create_project(client)
    iteration_id = _create_iteration(client, [project_id])
    requirement_id = _create_requirement(client, project_id, "Linked requirement")

    linked_requirements = client.post(
        f"/api/v1/iterations/{iteration_id}/requirements",
        json={"requirement_ids": [requirement_id]},
    )
    assert linked_requirements.status_code == 200

    generated = client.post(
        f"/api/v1/requirements/{requirement_id}/generate-task",
        json={"title": "Generated task from iteration requirement", "task_type": "development"},
    )
    assert generated.status_code == 200
    task_id = generated.json()["id"]

    detail = client.get(f"/api/v1/iterations/{iteration_id}/detail")
    assert detail.status_code == 200
    tasks = detail.json()["tasks"]
    assert {item["id"] for item in tasks} == {task_id}
    assert tasks[0]["requirement_id"] == requirement_id
    assert tasks[0]["project_id"] == project_id


def test_iteration_detail_includes_projects_from_linked_items_after_scope_changes(client: TestClient):
    original_project = _create_project(client, "Original linked item project")
    current_project = _create_project(client, "Current iteration project")
    iteration_id = _create_iteration(client, [original_project])
    requirement_id = _create_requirement(client, original_project, "Requirement kept after iteration project change")
    linked_requirements = client.post(
        f"/api/v1/iterations/{iteration_id}/requirements",
        json={"requirement_ids": [requirement_id]},
    )
    assert linked_requirements.status_code == 200
    updated = client.patch(f"/api/v1/iterations/{iteration_id}", json={"project_ids": [current_project]})
    assert updated.status_code == 200

    detail = client.get(f"/api/v1/iterations/{iteration_id}/detail")

    assert detail.status_code == 200
    project_ids = {item["id"] for item in detail.json()["projects"]}
    assert original_project in project_ids
    assert current_project in project_ids
    assert {item["id"] for item in detail.json()["requirements"]} == {requirement_id}


def test_generate_task_accepts_default_owner_from_iteration_page(client: TestClient):
    owner_id = _create_user(client)
    project_id = _create_project(client)
    requirement_id = _create_requirement(client, project_id, "Requirement without owner")

    generated = client.post(
        f"/api/v1/requirements/{requirement_id}/generate-task",
        json={"title": "Generated task with project owner", "owner_id": owner_id},
    )

    assert generated.status_code == 200
    assert generated.json()["owner_id"] == owner_id


def test_iteration_can_start_with_actual_start_date(client: TestClient):
    project_id = _create_project(client)
    iteration_id = _create_iteration(client, [project_id])

    started = client.post(
        f"/api/v1/iterations/{iteration_id}/start",
        json={"effective_time": "2026-06-12T09:30:00", "remark": "iteration kickoff"},
    )
    assert started.status_code == 200
    data = started.json()
    assert data["status"] == "active"
    assert data["actual_start_date"] == "2026-06-12"

    operations = client.get(f"/api/v1/iterations/{iteration_id}/status-operations")
    assert operations.status_code == 200
    assert operations.json()[0]["action"] == "start"
    assert operations.json()[0]["from_status"] == "planning"
    assert operations.json()[0]["to_status"] == "active"
    assert operations.json()[0]["remark"] == "iteration kickoff"


def test_iteration_can_finish_with_actual_end_date(client: TestClient):
    project_id = _create_project(client)
    iteration_id = _create_iteration(client, [project_id])
    started = client.post(
        f"/api/v1/iterations/{iteration_id}/start",
        json={"effective_time": "2026-06-12T09:30:00"},
    )
    assert started.status_code == 200

    finished = client.post(
        f"/api/v1/iterations/{iteration_id}/finish",
        json={"effective_time": "2026-06-20T18:00:00", "remark": "iteration finish"},
    )

    assert finished.status_code == 200
    data = finished.json()
    assert data["status"] == "finished"
    assert data["actual_end_date"] == "2026-06-20"

    operations = client.get(f"/api/v1/iterations/{iteration_id}/status-operations")
    assert operations.status_code == 200
    assert operations.json()[-1]["action"] == "finish"
    assert operations.json()[-1]["from_status"] == "active"
    assert operations.json()[-1]["to_status"] == "finished"
    assert operations.json()[-1]["remark"] == "iteration finish"
