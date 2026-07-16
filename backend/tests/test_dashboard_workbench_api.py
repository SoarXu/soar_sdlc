from datetime import datetime, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.session import SessionLocal
from app.models.bug import Bug
from app.models.object_watch import ObjectWatch
from app.models.project_member import ProjectMember
from app.models.role import Role, UserRole
from app.models.task import Task
from app.models.user import User
from app.models.workflow_definition import WorkflowState
from app.models.work_item_comment import WorkItemComment


def _create_user_with_role(username: str, role_key: str) -> tuple[int, str]:
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
        return user.id, create_access_token(user.username)
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


def _add_project_member(project_id: int, user_id: int, project_role: str) -> None:
    db = SessionLocal()
    try:
        db.add(
            ProjectMember(
                project_id=project_id,
                user_id=user_id,
                project_role=project_role,
                is_workbench_participant=True,
            )
        )
        db.commit()
    finally:
        db.close()


def _start_iteration(client: TestClient, iteration_id: int) -> None:
    response = client.post(
        f"/api/v1/workflow-runtime/iteration/{iteration_id}/transition",
        json={"action_key": "start", "payload": {"effective_time": "2026-06-24T10:00:00"}},
    )
    assert response.status_code == 200


def test_workbench_returns_default_queue_sections_for_pending_and_unassigned(client: TestClient):
    developer_id, developer_token = _create_user_with_role(f"queue_user_{uuid4().hex[:6]}", "developer")
    project_id = _create_project(client, "Queue workbench project")
    iteration_id = _create_iteration(client, project_id, "Queue iteration")
    _start_iteration(client, iteration_id)
    owned_task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
            "title": "Owned queue task",
            "owner_id": developer_id,
        },
    ).json()
    unassigned_bug = client.post(
        "/api/v1/bugs",
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
            "title": "Unassigned queue bug",
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

    response = client.get(
        "/api/v1/dashboard/workbench",
        headers={"Authorization": f"Bearer {developer_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["pending_handling"]["label"] == "待处理"
    pending_items = {item["id"]: item for item in data["pending_handling"]["items"]}
    assert owned_task["id"] in pending_items
    assert pending_items[owned_task["id"]]["iteration_id"] == iteration_id
    assert pending_items[owned_task["id"]]["iteration_name"] == "Queue iteration"
    assert data["unassigned"]["label"] == "未分派"
    assert unassigned_bug["id"] in {item["id"] for item in data["unassigned"]["items"]}
    assert "project_board" not in data
    assert "iterations" not in data


def test_workbench_queue_uses_state_category_and_status_name(client: TestClient):
    developer_id, developer_token = _create_user_with_role(f"state_queue_{uuid4().hex[:6]}", "developer")
    project_id = _create_project(client, "State identity queue project")
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "title": "State identity queue task", "owner_id": developer_id},
    ).json()
    _add_project_member(project_id, developer_id, "developer")

    db = SessionLocal()
    try:
        stored = db.query(Task).filter(Task.id == task["id"]).first()
        state = db.query(WorkflowState).filter(WorkflowState.id == stored.current_state_id).first()
        state.status_name = "等待本人处理"
        stored.status = "completed"
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/api/v1/dashboard/workbench",
        headers={"Authorization": f"Bearer {developer_token}"},
    )

    assert response.status_code == 200
    listed = next(item for item in response.json()["pending_handling"]["items"] if item["id"] == task["id"])
    assert listed["status"] == "等待本人处理"
    assert listed["status_name"] == "等待本人处理"
    assert listed["state_category"] == "start"


def test_workbench_returns_created_watched_mentioned_and_exception_center(client: TestClient):
    developer_id, developer_token = _create_user_with_role(f"follow_user_{uuid4().hex[:6]}", "developer")
    project_id = _create_project(client, "Follow project")
    iteration_id = _create_iteration(client, project_id, "Follow iteration")
    _start_iteration(client, iteration_id)
    created_requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
            "title": "Created requirement",
            "owner_id": developer_id,
        },
    ).json()
    watched_task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
            "title": "Watched task",
        },
    ).json()
    mentioned_bug = client.post(
        "/api/v1/bugs",
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
            "title": "Mentioned bug",
        },
    ).json()
    verified_bug = client.post(
        "/api/v1/bugs",
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
            "title": "Verified not closed bug",
            "owner_id": developer_id,
        },
    ).json()
    overdue_bug = client.post(
        "/api/v1/bugs",
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
            "title": "High priority unprocessed bug",
            "priority": "1",
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
        db.query(Bug).filter(Bug.id == verified_bug["id"]).update(
            {
                "status": "verified",
                "creator_id": developer_id,
                "create_time": datetime.now() - timedelta(hours=30),
            }
        )
        db.query(Bug).filter(Bug.id == mentioned_bug["id"]).update({"creator_id": developer_id})
        db.query(Bug).filter(Bug.id == overdue_bug["id"]).update(
            {"creator_id": developer_id, "create_time": datetime.now() - timedelta(hours=30)}
        )
        db.add(
            ObjectWatch(
                object_type="task",
                object_id=watched_task["id"],
                user_id=developer_id,
                source="manual",
                enabled=True,
            )
        )
        db.add(
            WorkItemComment(
                object_type="bug",
                object_id=mentioned_bug["id"],
                author_id=developer_id,
                body="@follow",
                mentioned_user_ids=[developer_id],
                mentions_metadata=[{"user_id": developer_id, "display_name": "Follow Developer"}],
            )
        )
        db.execute(
            __import__("sqlalchemy").text("update requirements set creator_id = :user_id where id = :id"),
            {"user_id": developer_id, "id": created_requirement["id"]},
        )
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/api/v1/dashboard/workbench",
        headers={"Authorization": f"Bearer {developer_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["created_by_me"]["label"] == "我发起的"
    assert created_requirement["id"] in {item["id"] for item in data["created_by_me"]["items"]}
    assert data["watched_by_me"]["label"] == "我关注的"
    assert watched_task["id"] in {item["id"] for item in data["watched_by_me"]["items"]}
    assert data["mentioned_me"]["label"] == "提到我的"
    assert mentioned_bug["id"] in {item["id"] for item in data["mentioned_me"]["items"]}
    assert "project_board" not in data
    assert "iterations" not in data
    assert data["exception_center"]["label"] == "异常中心"
    exception_ids = {(item["object_type"], item["id"]) for item in data["exception_center"]["items"]}
    assert ("bug", verified_bug["id"]) in exception_ids
    assert ("bug", overdue_bug["id"]) in exception_ids
    exception_item = next(
        item for item in data["exception_center"]["items"]
        if item["object_type"] == "bug" and item["id"] == verified_bug["id"]
    )
    assert exception_item["entered_at"]
    assert exception_item["threshold_hours"] == 24
    assert exception_item["threshold_count"] is None
    assert exception_item["overdue_hours"] >= 0


def test_authenticated_creates_immediately_appear_in_created_by_me(client: TestClient):
    user_id, token = _create_user_with_role(f"creator_user_{uuid4().hex[:6]}", "tester")
    project_id = _create_project(client, "Creator tracking project")
    _add_project_member(project_id, user_id, "tester")
    headers = {"Authorization": f"Bearer {token}"}

    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"Created requirement {uuid4().hex[:8]}"},
        headers=headers,
    )
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "title": f"Created task {uuid4().hex[:8]}"},
        headers=headers,
    )
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "title": f"Created bug {uuid4().hex[:8]}"},
        headers=headers,
    )
    test_run = client.post(
        "/api/v1/test-runs",
        json={"project_id": project_id, "name": f"Created test run {uuid4().hex[:8]}"},
        headers=headers,
    )

    for response in (requirement, task, bug, test_run):
        assert response.status_code in {200, 201}
        assert response.json()["creator_id"] == user_id

    workbench = client.get("/api/v1/dashboard/workbench", headers=headers).json()
    created_refs = {(item["object_type"], item["id"]) for item in workbench["created_by_me"]["items"]}
    assert {
        ("requirement", requirement.json()["id"]),
        ("task", task.json()["id"]),
        ("bug", bug.json()["id"]),
        ("test_run", test_run.json()["id"]),
    } <= created_refs


def test_workbench_move_endpoint_is_removed(client: TestClient):
    response = client.post(
        "/api/v1/dashboard/workbench/move",
        json={"object_type": "task", "object_id": 1, "target_iteration_id": 1},
    )

    assert response.status_code == 404


def test_workbench_requires_authentication(client: TestClient):
    response = client.get(
        "/api/v1/dashboard/workbench",
        headers={"X-Test-No-Auth": "1"},
    )

    assert response.status_code == 401
