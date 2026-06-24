from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.core.security import get_password_hash
from app.models.role import Role, UserRole
from app.models.user import User


def _create_user_with_role(username: str, role_key: str) -> int:
    db = SessionLocal()
    try:
        role = db.query(Role).filter(Role.role_key == role_key).first()
        if not role:
            role = Role(role_key=role_key, role_name=role_key, enabled=True, is_system=True)
            db.add(role)
            db.flush()
        user = User(
            username=username,
            full_name=username,
            password_hash=get_password_hash("User123456"),
            is_active=True,
        )
        db.add(user)
        db.flush()
        db.add(UserRole(user_id=user.id, role_id=role.id))
        db.commit()
        return user.id
    finally:
        db.close()


def _create_project(client: TestClient, name: str | None = None) -> int:
    response = client.post("/api/v1/projects", json={"name": name or f"Project-{uuid4().hex[:8]}"})
    assert response.status_code == 200
    return response.json()["id"]


def _create_iteration(client: TestClient, project_id: int, name: str | None = None) -> int:
    response = client.post(
        "/api/v1/iterations",
        json={"project_ids": [project_id], "name": name or f"Iteration-{uuid4().hex[:8]}"},
    )
    assert response.status_code == 200
    return response.json()["id"]


def test_workbench_groups_items_by_iteration_and_supports_test_case_iteration(client: TestClient):
    project_id = _create_project(client, "Workbench Project")
    iteration_id = _create_iteration(client, project_id, "Workbench Iteration")

    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": "Workbench Requirement"},
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": "Workbench Task"},
    ).json()
    test_case = client.post(
        "/api/v1/test-cases",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": "Workbench Case"},
    ).json()
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": "Workbench Bug"},
    ).json()

    response = client.get("/api/v1/dashboard/workbench")

    assert response.status_code == 200
    boards = response.json()["iterations"]
    board = next(item for item in boards if item["id"] == iteration_id)
    assert {item["id"] for item in board["requirements"]} == {requirement["id"]}
    assert {item["id"] for item in board["tasks"]} == {task["id"]}
    assert {item["id"] for item in board["test_cases"]} == {test_case["id"]}
    assert {item["id"] for item in board["bugs"]} == {bug["id"]}
    assert board["counts"] == {"requirements": 1, "tasks": 1, "test_cases": 1, "bugs": 1}


def test_developer_workbench_defaults_to_owned_active_iteration_work(client: TestClient):
    developer_id = _create_user_with_role("developer_user", "developer")
    other_user_id = _create_user_with_role("other_developer", "developer")
    project_id = _create_project(client, "Developer Workbench Project")
    iteration_id = _create_iteration(client, project_id, "Developer Active Iteration")
    client.post(f"/api/v1/iterations/{iteration_id}/start", json={"effective_time": "2026-06-24T10:00:00"})
    mine = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": "My active task", "owner_id": developer_id},
    ).json()
    client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": "Other active task", "owner_id": other_user_id},
    )

    response = client.get(f"/api/v1/dashboard/workbench?user_id={developer_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["view_mode"] == "developer"
    board = next(item for item in data["iterations"] if item["id"] == iteration_id)
    assert {item["id"] for item in board["tasks"]} == {mine["id"]}
    assert board["test_cases"] == []


def test_tester_workbench_includes_linked_cases_with_completion_marker(client: TestClient):
    tester_id = _create_user_with_role("tester_user", "tester")
    project_id = _create_project(client, "Tester Workbench Project")
    iteration_id = _create_iteration(client, project_id, "Tester Active Iteration")
    client.post(f"/api/v1/iterations/{iteration_id}/start", json={"effective_time": "2026-06-24T10:00:00"})
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": "Done requirement", "owner_id": tester_id},
    ).json()
    client.post(f"/api/v1/requirements/{requirement['id']}/activate")
    client.post(f"/api/v1/requirements/{requirement['id']}/complete")
    test_case = client.post(
        "/api/v1/test-cases",
        json={
            "project_id": project_id,
            "requirement_id": requirement["id"],
            "title": "Regression case for done requirement",
            "default_tester_id": tester_id,
        },
    ).json()

    response = client.get(f"/api/v1/dashboard/workbench?user_id={tester_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["view_mode"] == "tester"
    board = next(item for item in data["iterations"] if item["id"] == iteration_id)
    case = next(item for item in board["test_cases"] if item["id"] == test_case["id"])
    assert case["marker"] == "待回归"


def test_workbench_iteration_includes_related_projects(client: TestClient):
    project_id = _create_project(client, "Scope Visible Project")
    iteration_id = _create_iteration(client, project_id, "Scope Visible Iteration")

    response = client.get("/api/v1/dashboard/workbench")

    assert response.status_code == 200
    board = next(item for item in response.json()["iterations"] if item["id"] == iteration_id)
    assert board["projects"] == [{"id": project_id, "name": "Scope Visible Project"}]
    assert board["create_time"]


def test_workbench_includes_empty_iterations(client: TestClient):
    project_id = _create_project(client, "Empty Board Project")
    iteration_id = _create_iteration(client, project_id, "Empty Board Iteration")

    response = client.get("/api/v1/dashboard/workbench")

    assert response.status_code == 200
    board = next(item for item in response.json()["iterations"] if item["id"] == iteration_id)
    assert board["counts"] == {"requirements": 0, "tasks": 0, "test_cases": 0, "bugs": 0}


def test_workbench_includes_tasks_and_cases_from_linked_requirements(client: TestClient):
    project_id = _create_project(client, "Requirement Derived Workbench Project")
    iteration_id = _create_iteration(client, project_id, "Requirement Derived Workbench Iteration")
    requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
            "title": "Requirement that carries implementation and case",
        },
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "requirement_id": requirement["id"],
            "title": "Task inherited from requirement iteration",
        },
    ).json()
    test_case = client.post(
        "/api/v1/test-cases",
        json={
            "project_id": project_id,
            "requirement_id": requirement["id"],
            "title": "Case inherited from requirement iteration",
        },
    ).json()

    response = client.get("/api/v1/dashboard/workbench")

    assert response.status_code == 200
    board = next(item for item in response.json()["iterations"] if item["id"] == iteration_id)
    assert {item["id"] for item in board["tasks"]} == {task["id"]}
    assert {item["id"] for item in board["test_cases"]} == {test_case["id"]}
    assert board["counts"]["tasks"] == 1
    assert board["counts"]["test_cases"] == 1


def test_workbench_move_updates_iteration_id_for_supported_objects(client: TestClient):
    project_id = _create_project(client, "Move Project")
    source_iteration = _create_iteration(client, project_id, "Source Iteration")
    target_iteration = _create_iteration(client, project_id, "Target Iteration")
    test_case = client.post(
        "/api/v1/test-cases",
        json={"project_id": project_id, "iteration_id": source_iteration, "title": "Movable Case"},
    ).json()

    moved = client.post(
        "/api/v1/dashboard/workbench/move",
        json={"object_type": "test_case", "object_id": test_case["id"], "target_iteration_id": target_iteration},
    )

    assert moved.status_code == 200
    assert moved.json()["iteration_id"] == target_iteration
    detail = client.get(f"/api/v1/test-cases/{test_case['id']}")
    assert detail.status_code == 200
    assert detail.json()["iteration_id"] == target_iteration


def test_workbench_move_rejects_items_outside_target_iteration_project_scope(client: TestClient):
    source_project = _create_project(client, "Source Project")
    target_project = _create_project(client, "Target Project")
    target_iteration = _create_iteration(client, target_project, "Target Iteration")
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": source_project, "title": "Out of scope requirement"},
    ).json()

    moved = client.post(
        "/api/v1/dashboard/workbench/move",
        json={"object_type": "requirement", "object_id": requirement["id"], "target_iteration_id": target_iteration},
    )

    assert moved.status_code == 400
    assert "项目范围" in moved.json()["detail"]


def test_workbench_shows_items_by_iteration_even_when_lifecycle_phase_differs(client: TestClient):
    project_id = _create_project(client, "Phase Project")
    iteration_id = _create_iteration(client, project_id, "Development Iteration")
    visible_requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
            "title": "Development requirement",
            "lifecycle_phase": "development",
        },
    ).json()
    different_phase_requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
            "title": "Maintenance requirement",
            "lifecycle_phase": "maintenance",
        },
    ).json()
    db = SessionLocal()
    try:
        from sqlalchemy import text

        db.execute(text("update requirements set lifecycle_phase = 'maintenance' where id = :id"), {"id": different_phase_requirement["id"]})
        db.commit()
    finally:
        db.close()

    response = client.get("/api/v1/dashboard/workbench")

    assert response.status_code == 200
    board = next(item for item in response.json()["iterations"] if item["id"] == iteration_id)
    requirement_ids = {item["id"] for item in board["requirements"]}
    assert visible_requirement["id"] in requirement_ids
    assert different_phase_requirement["id"] in requirement_ids


def test_workbench_uses_iteration_membership_not_lifecycle_phase(client: TestClient):
    project_id = _create_project(client, "Iteration Membership Project")
    iteration_id = _create_iteration(client, project_id, "Iteration Membership Board")
    requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
            "title": "Requirement visible by iteration membership",
            "lifecycle_phase": "development",
        },
    ).json()
    db = SessionLocal()
    try:
        from sqlalchemy import text

        db.execute(text("update iterations set lifecycle_phase = 'maintenance' where id = :id"), {"id": iteration_id})
        db.execute(text("update requirements set lifecycle_phase = 'development' where id = :id"), {"id": requirement["id"]})
        db.commit()
    finally:
        db.close()

    response = client.get("/api/v1/dashboard/workbench")

    assert response.status_code == 200
    board = next(item for item in response.json()["iterations"] if item["id"] == iteration_id)
    assert requirement["id"] in {item["id"] for item in board["requirements"]}


def test_requirement_and_task_can_be_completed_with_status_history(client: TestClient):
    project_id = _create_project(client, "Completion Project")
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": "Completable requirement"},
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "title": "Completable task"},
    ).json()

    completed_requirement = client.post(f"/api/v1/requirements/{requirement['id']}/complete")
    completed_task = client.post(f"/api/v1/tasks/{task['id']}/complete")

    assert completed_requirement.status_code == 200
    assert completed_requirement.json()["status"] == "done"
    assert completed_task.status_code == 200
    assert completed_task.json()["status"] == "done"
    requirement_history = client.get(f"/api/v1/requirements/{requirement['id']}/status-operations").json()
    task_history = client.get(f"/api/v1/tasks/{task['id']}/status-operations").json()
    assert requirement_history[-1]["action"] == "complete"
    assert task_history[-1]["action"] == "complete"


def test_requirement_complete_requires_linked_tasks_done(client: TestClient):
    project_id = _create_project(client, "Requirement Guard Project")
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": "Requirement with open task"},
    ).json()
    client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "requirement_id": requirement["id"], "title": "Open linked task"},
    )

    completed = client.post(f"/api/v1/requirements/{requirement['id']}/complete")

    assert completed.status_code == 400
    assert "关联任务" in completed.json()["detail"]
