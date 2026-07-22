from datetime import datetime, timedelta
from unittest.mock import Mock
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
from app.models.workflow_definition import WorkflowState, WorkflowTransition
from app.models.work_item_comment import WorkItemComment
from app.services.dashboard_service import _terminal_iteration_open_item_refs


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


def test_workbench_project_scope_does_not_expand_between_parent_and_child(client: TestClient):
    parent_member_id, parent_token = _create_user_with_role(f"parent_scope_{uuid4().hex[:6]}", "developer")
    child_member_id, child_token = _create_user_with_role(f"child_scope_{uuid4().hex[:6]}", "developer")
    parent_id = _create_project(client, "Isolated parent")
    child = client.post("/api/v1/projects", json={"name": "Isolated child", "parent_id": parent_id}).json()
    parent_iteration = _create_iteration(client, parent_id, "Parent active")
    child_iteration = _create_iteration(client, child["id"], "Child active")
    _start_iteration(client, parent_iteration)
    _start_iteration(client, child_iteration)
    parent_task = client.post("/api/v1/tasks", json={"project_id": parent_id, "iteration_id": parent_iteration, "title": "Parent only"}).json()
    child_task = client.post("/api/v1/tasks", json={"project_id": child["id"], "iteration_id": child_iteration, "title": "Child only"}).json()
    _add_project_member(parent_id, parent_member_id, "developer")
    _add_project_member(child["id"], child_member_id, "developer")

    parent_items = client.get("/api/v1/dashboard/workbench", headers={"Authorization": f"Bearer {parent_token}"}).json()["unassigned"]["items"]
    child_items = client.get("/api/v1/dashboard/workbench", headers={"Authorization": f"Bearer {child_token}"}).json()["unassigned"]["items"]

    assert {item["id"] for item in parent_items if item["object_type"] == "task"} >= {parent_task["id"]}
    assert child_task["id"] not in {item["id"] for item in parent_items}
    assert {item["id"] for item in child_items if item["object_type"] == "task"} >= {child_task["id"]}
    assert parent_task["id"] not in {item["id"] for item in child_items}


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
    iteration_id = _create_iteration(client, project_id, "State identity queue iteration")
    _start_iteration(client, iteration_id)
    task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
            "title": "State identity queue task",
            "owner_id": developer_id,
        },
    ).json()
    _add_project_member(project_id, developer_id, "developer")

    db = SessionLocal()
    try:
        stored = db.query(Task).filter(Task.id == task["id"]).first()
        state = db.query(WorkflowState).filter(WorkflowState.id == stored.current_state_id).first()
        renamed_state = WorkflowState(
            definition_id=state.definition_id,
            status_name="等待本人处理",
            category=state.category,
            enabled=True,
        )
        db.add(renamed_state)
        db.flush()
        stored.current_state_id = renamed_state.id
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
    watched_test_case = client.post(
        "/api/v1/test-cases",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": "Watched test case"},
    ).json()
    mentioned_test_run = client.post(
        "/api/v1/test-runs",
        json={"project_id": project_id, "iteration_id": iteration_id, "name": "Mentioned test run"},
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
        verified_state_id = db.query(WorkflowTransition.to_state_id).filter(
            WorkflowTransition.definition_id == verified_bug["workflow_definition_id"],
            WorkflowTransition.action_key == "verification_passed",
        ).scalar()
        assert verified_state_id is not None
        db.query(Bug).filter(Bug.id == verified_bug["id"]).update(
            {
                "current_state_id": verified_state_id,
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
            ObjectWatch(
                object_type="requirement",
                object_id=created_requirement["id"],
                user_id=developer_id,
                source="manual",
                enabled=True,
            )
        )
        db.add(
            ObjectWatch(
                object_type="bug",
                object_id=mentioned_bug["id"],
                user_id=developer_id,
                source="manual",
                enabled=True,
            )
        )
        db.add(
            ObjectWatch(
                object_type="test_case",
                object_id=watched_test_case["id"],
                user_id=developer_id,
                source="manual",
                enabled=True,
            )
        )
        db.add(
            ObjectWatch(
                object_type="test_run",
                object_id=mentioned_test_run["id"],
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
        for object_type, object_id in (
            ("requirement", created_requirement["id"]),
            ("task", watched_task["id"]),
            ("test_case", watched_test_case["id"]),
        ):
            db.add(
                WorkItemComment(
                    object_type=object_type,
                    object_id=object_id,
                    author_id=developer_id,
                    body="@follow",
                    mentioned_user_ids=[developer_id],
                    mentions_metadata=[{"user_id": developer_id, "display_name": "Follow Developer"}],
                )
            )
        db.add(
            WorkItemComment(
                object_type="test_run",
                object_id=mentioned_test_run["id"],
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
    watched_refs = {(item["object_type"], item["id"]) for item in data["watched_by_me"]["items"]}
    assert {
        ("requirement", created_requirement["id"]),
        ("task", watched_task["id"]),
        ("bug", mentioned_bug["id"]),
    } <= watched_refs
    assert {
        ("test_case", watched_test_case["id"]),
        ("test_run", mentioned_test_run["id"]),
    }.isdisjoint(watched_refs)
    assert data["mentioned_me"]["label"] == "提到我的"
    mentioned_refs = {(item["object_type"], item["id"]) for item in data["mentioned_me"]["items"]}
    assert {
        ("requirement", created_requirement["id"]),
        ("task", watched_task["id"]),
        ("bug", mentioned_bug["id"]),
    } <= mentioned_refs
    assert {
        ("test_case", watched_test_case["id"]),
        ("test_run", mentioned_test_run["id"]),
    }.isdisjoint(mentioned_refs)
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
    iteration_id = _create_iteration(client, project_id, "Creator tracking iteration")
    _start_iteration(client, iteration_id)
    _add_project_member(project_id, user_id, "tester")
    headers = {"Authorization": f"Bearer {token}"}

    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": f"Created requirement {uuid4().hex[:8]}"},
        headers=headers,
    )
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": f"Created task {uuid4().hex[:8]}"},
        headers=headers,
    )
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": f"Created bug {uuid4().hex[:8]}"},
        headers=headers,
    )
    test_run = client.post(
        "/api/v1/test-runs",
        json={"project_id": project_id, "iteration_id": iteration_id, "name": f"Created test run {uuid4().hex[:8]}"},
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
    } <= created_refs
    assert ("test_run", test_run.json()["id"]) not in created_refs


def test_workbench_scopes_execution_to_active_iterations_and_excludes_uniterated_items(client: TestClient):
    user_id, token = _create_user_with_role(f"active_scope_{uuid4().hex[:6]}", "product_manager")
    project_id = _create_project(client, "Active scope project")
    _add_project_member(project_id, user_id, "product_manager")
    planning_iteration_id = _create_iteration(client, project_id, "Planning iteration")
    active_iteration_id = _create_iteration(client, project_id, "Active iteration")
    _start_iteration(client, active_iteration_id)
    headers = {"Authorization": f"Bearer {token}"}

    active_requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project_id,
            "iteration_id": active_iteration_id,
            "title": "Active assigned requirement",
            "owner_id": user_id,
        },
        headers=headers,
    ).json()
    active_unassigned_task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "iteration_id": active_iteration_id,
            "title": "Active unassigned task",
        },
        headers=headers,
    ).json()
    planning_task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "iteration_id": planning_iteration_id,
            "title": "Planning assigned task",
            "owner_id": user_id,
        },
        headers=headers,
    ).json()
    uniterated_requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project_id,
            "title": "Uniterated requirement",
            "owner_id": user_id,
        },
        headers=headers,
    ).json()
    uniterated_task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "title": "Uniterated task"},
        headers=headers,
    ).json()
    uniterated_bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "title": "Uniterated bug", "owner_id": user_id},
        headers=headers,
    ).json()

    db = SessionLocal()
    try:
        db.add(
            ObjectWatch(
                object_type="task",
                object_id=uniterated_task["id"],
                user_id=user_id,
                source="manual",
                enabled=True,
            )
        )
        db.add(
            WorkItemComment(
                object_type="bug",
                object_id=uniterated_bug["id"],
                author_id=user_id,
                body="@active_scope",
                mentioned_user_ids=[user_id],
                mentions_metadata=[{"user_id": user_id, "display_name": "Active scope user"}],
            )
        )
        db.commit()
    finally:
        db.close()

    data = client.get("/api/v1/dashboard/workbench", headers=headers).json()
    pending_refs = {(item["object_type"], item["id"]) for item in data["pending_handling"]["items"]}
    unassigned_refs = {(item["object_type"], item["id"]) for item in data["unassigned"]["items"]}
    created_refs = {(item["object_type"], item["id"]) for item in data["created_by_me"]["items"]}

    assert "unplanned" not in data
    assert pending_refs == {("requirement", active_requirement["id"])}
    assert unassigned_refs == {("task", active_unassigned_task["id"])}
    assert ("requirement", active_requirement["id"]) in created_refs
    assert ("task", planning_task["id"]) not in created_refs
    uniterated_refs = {
        ("requirement", uniterated_requirement["id"]),
        ("task", uniterated_task["id"]),
        ("bug", uniterated_bug["id"]),
    }
    for section in (
        "pending_handling",
        "unassigned",
        "created_by_me",
        "watched_by_me",
        "mentioned_me",
        "exception_center",
    ):
        section_refs = {(item["object_type"], item["id"]) for item in data[section]["items"]}
        assert uniterated_refs.isdisjoint(section_refs)


def test_workbench_empty_project_scope_is_not_all_projects(client: TestClient):
    _, outsider_token = _create_user_with_role(f"scope_outsider_{uuid4().hex[:6]}", "developer")
    project_id = _create_project(client, "Invisible workbench project")
    iteration_id = _create_iteration(client, project_id, "Invisible active iteration")
    _start_iteration(client, iteration_id)
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": "Invisible unassigned task"},
    ).json()

    data = client.get(
        "/api/v1/dashboard/workbench",
        headers={"Authorization": f"Bearer {outsider_token}"},
    ).json()
    visible_refs = {
        (item["object_type"], item["id"])
        for section in ("pending_handling", "unassigned", "exception_center")
        for item in data[section]["items"]
    }

    assert ("task", task["id"]) not in visible_refs


def test_terminal_iteration_integrity_scan_short_circuits_empty_project_scope():
    db = Mock()
    db.query.side_effect = AssertionError("empty project scope must not query historical work items")

    assert _terminal_iteration_open_item_refs(db, set()) == []
    db.query.assert_not_called()


def test_system_admin_workbench_has_explicit_all_project_scope(client: TestClient):
    _, admin_token = _create_user_with_role(f"scope_admin_{uuid4().hex[:6]}", "system_admin")
    project_id = _create_project(client, "Admin workbench project")
    iteration_id = _create_iteration(client, project_id, "Admin active iteration")
    _start_iteration(client, iteration_id)
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": "Admin visible unassigned task"},
    ).json()

    data = client.get(
        "/api/v1/dashboard/workbench",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()

    assert ("task", task["id"]) in {
        (item["object_type"], item["id"]) for item in data["unassigned"]["items"]
    }


def test_terminal_iteration_open_item_is_only_reported_as_integrity_exception(client: TestClient):
    user_id, token = _create_user_with_role(f"integrity_user_{uuid4().hex[:6]}", "developer")
    project_id = _create_project(client, "Integrity exception project")
    _add_project_member(project_id, user_id, "developer")
    iteration_id = _create_iteration(client, project_id, "Completed integrity iteration")
    _start_iteration(client, iteration_id)
    completed = client.post(
        f"/api/v1/workflow-runtime/iteration/{iteration_id}/transition",
        json={"action_key": "complete"},
    )
    assert completed.status_code == 200
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "title": "Legacy open task", "owner_id": user_id},
    ).json()
    db = SessionLocal()
    try:
        db.query(Task).filter(Task.id == task["id"]).update({"iteration_id": iteration_id})
        db.commit()
    finally:
        db.close()

    data = client.get(
        "/api/v1/dashboard/workbench",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    pending_refs = {(item["object_type"], item["id"]) for item in data["pending_handling"]["items"]}
    exception_item = next(
        item
        for item in data["exception_center"]["items"]
        if item["object_type"] == "task" and item["id"] == task["id"]
    )

    assert ("task", task["id"]) not in pending_refs
    assert exception_item["exception_key"] == "terminal_iteration_open_item"


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
