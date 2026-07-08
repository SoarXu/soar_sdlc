from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.core.security import get_password_hash
from app.models.role import Role, UserRole
from app.models.user import User
from app.models.project_member import ProjectMember


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


def _create_child_project(client: TestClient, parent_id: int, name: str | None = None) -> int:
    response = client.post(
        "/api/v1/projects",
        json={"name": name or f"Project-{uuid4().hex[:8]}", "parent_id": parent_id},
    )
    assert response.status_code == 200
    return response.json()["id"]


def _create_iteration(client: TestClient, project_id: int, name: str | None = None) -> int:
    response = client.post(
        "/api/v1/iterations",
        json={"project_ids": [project_id], "name": name or f"Iteration-{uuid4().hex[:8]}"},
    )
    assert response.status_code == 200
    return response.json()["id"]


def _start_iteration(client: TestClient, iteration_id: int) -> None:
    response = client.post(f"/api/v1/iterations/{iteration_id}/start", json={"effective_time": "2026-06-24T10:00:00"})
    assert response.status_code == 200


def test_workbench_groups_items_by_iteration_and_supports_test_case_iteration(client: TestClient):
    project_id = _create_project(client, "Workbench Project")
    iteration_id = _create_iteration(client, project_id, "Workbench Iteration")
    _start_iteration(client, iteration_id)

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


def test_workbench_returns_all_iteration_statuses(client: TestClient):
    project_id = _create_project(client, "All Status Workbench Project")
    active_iteration_id = _create_iteration(client, project_id, "Active Workbench Iteration")
    planning_iteration_id = _create_iteration(client, project_id, "Planning Workbench Iteration")
    client.post(f"/api/v1/iterations/{active_iteration_id}/start", json={"effective_time": "2026-06-24T10:00:00"})
    client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "iteration_id": active_iteration_id, "title": "Active iteration requirement"},
    )
    client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "iteration_id": planning_iteration_id, "title": "Planning iteration requirement"},
    )

    response = client.get("/api/v1/dashboard/workbench")

    assert response.status_code == 200
    board_ids = {item["id"] for item in response.json()["iterations"]}
    assert active_iteration_id in board_ids
    assert planning_iteration_id in board_ids


def test_developer_workbench_scope_includes_non_active_project_iterations(client: TestClient):
    developer_id = _create_user_with_role(f"developer_scope_{uuid4().hex[:6]}", "developer")
    project_id = _create_project(client, "Developer Planning Scope Project")
    planning_iteration_id = _create_iteration(client, project_id, "Developer Planning Iteration")
    requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project_id,
            "iteration_id": planning_iteration_id,
            "title": "Planning iteration requirement",
            "owner_id": developer_id,
        },
    ).json()

    db = SessionLocal()
    try:
        db.add(
            ProjectMember(
                project_id=project_id,
                user_id=developer_id,
                project_role="developer",
                is_workbench_participant=True,
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get(f"/api/v1/dashboard/workbench?user_id={developer_id}")

    assert response.status_code == 200
    data = response.json()
    board = next(item for item in data["iterations"] if item["id"] == planning_iteration_id)
    assert board["status"] == "planning"
    assert {item["id"] for item in board["requirements"]} == {requirement["id"]}


def test_developer_workbench_defaults_to_project_member_active_iteration_work(client: TestClient):
    developer_id = _create_user_with_role("developer_user", "developer")
    other_user_id = _create_user_with_role("other_developer", "developer")
    outsider_id = _create_user_with_role("outside_developer", "developer")
    project_id = _create_project(client, "Developer Workbench Project")
    iteration_id = _create_iteration(client, project_id, "Developer Active Iteration")
    _start_iteration(client, iteration_id)
    requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
            "title": "Team visible requirement",
            "owner_id": developer_id,
        },
    ).json()
    owned_task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": "My active task", "owner_id": developer_id},
    ).json()
    other_task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": "Other active task", "owner_id": other_user_id},
    ).json()

    db = SessionLocal()
    try:
        db.add(
            ProjectMember(
                project_id=project_id,
                user_id=developer_id,
                project_role="developer",
                is_workbench_participant=True,
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get(f"/api/v1/dashboard/workbench?user_id={developer_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["view_mode"] == "mine"
    board = next(item for item in data["iterations"] if item["id"] == iteration_id)
    assert {item["id"] for item in board["requirements"]} == {requirement["id"]}
    assert {item["id"] for item in board["tasks"]} == {owned_task["id"]}
    assert other_task["id"] not in {item["id"] for item in board["tasks"]}
    assert board["test_cases"] == []

    outsider_response = client.get(f"/api/v1/dashboard/workbench?user_id={outsider_id}")
    assert outsider_response.status_code == 200
    outsider_board_ids = {item["id"] for item in outsider_response.json()["iterations"]}
    assert iteration_id not in outsider_board_ids


def test_development_lead_workbench_is_limited_to_project_team_scope(client: TestClient):
    lead_id = _create_user_with_role(f"lead_user_{uuid4().hex[:6]}", "development_lead")
    scoped_project_id = _create_project(client, "Lead Scoped Project")
    outside_project_id = _create_project(client, "Lead Outside Project")
    scoped_iteration_id = _create_iteration(client, scoped_project_id, "Lead Scoped Iteration")
    outside_iteration_id = _create_iteration(client, outside_project_id, "Lead Outside Iteration")
    _start_iteration(client, scoped_iteration_id)
    _start_iteration(client, outside_iteration_id)
    scoped_requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": scoped_project_id, "iteration_id": scoped_iteration_id, "title": "Lead scoped requirement"},
    ).json()
    client.post(
        "/api/v1/requirements",
        json={"project_id": outside_project_id, "iteration_id": outside_iteration_id, "title": "Lead outside requirement"},
    )

    db = SessionLocal()
    try:
        db.add(
            ProjectMember(
                project_id=scoped_project_id,
                user_id=lead_id,
                project_role="tech_lead",
                is_workbench_participant=True,
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get(f"/api/v1/dashboard/workbench?user_id={lead_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["view_mode"] == "lead"
    board_ids = {item["id"] for item in data["iterations"]}
    assert scoped_iteration_id in board_ids
    assert outside_iteration_id not in board_ids
    board = next(item for item in data["iterations"] if item["id"] == scoped_iteration_id)
    assert {item["id"] for item in board["requirements"]} == {scoped_requirement["id"]}


def test_tester_workbench_includes_linked_cases_without_completion_marker(client: TestClient):
    tester_id = _create_user_with_role("tester_user", "tester")
    project_id = _create_project(client, "Tester Workbench Project")
    iteration_id = _create_iteration(client, project_id, "Tester Active Iteration")
    _start_iteration(client, iteration_id)
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
    client.post(
        f"/api/v1/test-cases/{test_case['id']}/executions",
        json={"steps_result_json": [{"step": "open", "expected": "ok", "result": "failed"}]},
    )
    db = SessionLocal()
    try:
        db.add(
            ProjectMember(
                project_id=project_id,
                user_id=tester_id,
                project_role="tester",
                is_workbench_participant=True,
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get(f"/api/v1/dashboard/workbench?user_id={tester_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["view_mode"] == "mine"
    board = next(item for item in data["iterations"] if item["id"] == iteration_id)
    case = next(item for item in board["test_cases"] if item["id"] == test_case["id"])
    assert "marker" not in case
    assert case["last_execute_result"] == "failed"
    assert case["last_execute_time"]


def test_workbench_iteration_includes_related_projects(client: TestClient):
    project_id = _create_project(client, "Scope Visible Project")
    iteration_id = _create_iteration(client, project_id, "Scope Visible Iteration")
    _start_iteration(client, iteration_id)

    response = client.get("/api/v1/dashboard/workbench")

    assert response.status_code == 200
    board = next(item for item in response.json()["iterations"] if item["id"] == iteration_id)
    assert board["projects"] == [{"id": project_id, "name": "Scope Visible Project"}]
    assert board["create_time"]


def test_workbench_iteration_project_scope_includes_child_items_without_extra_columns(client: TestClient):
    parent_project_id = _create_project(client, "InnovateX运维")
    child_project_id = _create_child_project(client, parent_project_id, "物料管理")
    iteration_id = _create_iteration(client, parent_project_id, "InnovateX运维-迭代1.4.6")
    _start_iteration(client, iteration_id)
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": child_project_id, "iteration_id": iteration_id, "title": "子项目需求"},
    ).json()

    response = client.get("/api/v1/dashboard/workbench")

    assert response.status_code == 200
    board = next(item for item in response.json()["iterations"] if item["id"] == iteration_id)
    assert board["projects"] == [{"id": parent_project_id, "name": "InnovateX运维"}]
    assert set(board["scoped_project_ids"]) == {parent_project_id, child_project_id}
    assert {item["id"] for item in board["requirements"]} == {requirement["id"]}


def test_child_project_member_workbench_includes_parent_iteration_with_child_items(client: TestClient):
    user_id = _create_user_with_role(f"child_member_{uuid4().hex[:6]}", "developer")
    parent_project_id = _create_project(client, "InnovateX运维")
    child_project_id = _create_child_project(client, parent_project_id, "物料管理")
    iteration_id = _create_iteration(client, parent_project_id, "InnovateX运维-迭代1.4.6")
    _start_iteration(client, iteration_id)
    requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": child_project_id,
            "iteration_id": iteration_id,
            "title": "子项目成员可见需求",
            "owner_id": user_id,
        },
    ).json()
    db = SessionLocal()
    try:
        db.add(
            ProjectMember(
                project_id=child_project_id,
                user_id=user_id,
                project_role="developer",
                is_workbench_participant=True,
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get(f"/api/v1/dashboard/workbench?user_id={user_id}")

    assert response.status_code == 200
    board = next(item for item in response.json()["iterations"] if item["id"] == iteration_id)
    assert board["projects"] == [{"id": parent_project_id, "name": "InnovateX运维"}]
    assert set(board["scoped_project_ids"]) == {parent_project_id, child_project_id}
    assert {item["id"] for item in board["requirements"]} == {requirement["id"]}


def test_workbench_includes_empty_iterations(client: TestClient):
    project_id = _create_project(client, "Empty Board Project")
    iteration_id = _create_iteration(client, project_id, "Empty Board Iteration")
    _start_iteration(client, iteration_id)

    response = client.get("/api/v1/dashboard/workbench")

    assert response.status_code == 200
    board = next(item for item in response.json()["iterations"] if item["id"] == iteration_id)
    assert board["counts"] == {"requirements": 0, "tasks": 0, "test_cases": 0, "bugs": 0}


def test_workbench_includes_tasks_and_cases_from_linked_requirements(client: TestClient):
    project_id = _create_project(client, "Requirement Derived Workbench Project")
    iteration_id = _create_iteration(client, project_id, "Requirement Derived Workbench Iteration")
    _start_iteration(client, iteration_id)
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
    _start_iteration(client, iteration_id)
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
    _start_iteration(client, iteration_id)
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
    assert completed_requirement.json()["status"] == "pending_validation"
    assert completed_task.status_code == 200
    assert completed_task.json()["status"] == "done"
    requirement_history = client.get(f"/api/v1/requirements/{requirement['id']}/status-operations").json()
    task_history = client.get(f"/api/v1/tasks/{task['id']}/status-operations").json()
    assert requirement_history[-1]["action"] == "submit_validation"
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
