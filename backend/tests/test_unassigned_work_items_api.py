from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.session import SessionLocal
from app.models.project_member import ProjectMember
from app.models.role import Role, UserRole
from app.models.task import Task
from app.models.user import User
from app.models.workflow_definition import WorkflowState


def _create_user(full_name: str, role_key: str | None = None) -> tuple[int, str]:
    db = SessionLocal()
    try:
        user = User(
            username=f"work_item_{uuid4().hex[:8]}",
            full_name=full_name,
            password_hash=get_password_hash("User123456"),
            is_active=True,
        )
        db.add(user)
        db.flush()
        if role_key:
            role = db.query(Role).filter(Role.role_key == role_key).first()
            if not role:
                role = Role(role_key=role_key, role_name=role_key, enabled=True, is_system=True)
                db.add(role)
                db.flush()
            db.add(UserRole(user_id=user.id, role_id=role.id))
        db.commit()
        return user.id, create_access_token(user.username)
    finally:
        db.close()


def _add_project_member(project_id: int, user_id: int, project_role: str, sort_order: int = 0) -> None:
    db = SessionLocal()
    try:
        db.add(
            ProjectMember(
                project_id=project_id,
                user_id=user_id,
                project_role=project_role,
                sort_order=sort_order,
                is_workbench_participant=True,
            )
        )
        db.commit()
    finally:
        db.close()


def _create_project(client: TestClient) -> tuple[int, int]:
    config = client.post(
        "/api/v1/assignee-rule-configs",
        json={
            "name": f"Work Item Config {uuid4().hex[:8]}",
            "requirement_owner_roles": "",
            "task_owner_roles": "",
            "test_case_tester_roles": "tester",
            "test_run_owner_roles": "tester",
            "bug_owner_roles": "",
            "creation_mode": "template",
            "template_source": {"source_type": "system", "source_id": "system-standard"},
        },
    )
    assert config.status_code == 201
    enabled = client.post(f"/api/v1/assignee-rule-configs/{config.json()['id']}/enable")
    assert enabled.status_code == 200, enabled.text
    project = client.post(
        "/api/v1/projects",
        json={"name": f"Work Item Project {uuid4().hex[:8]}", "assignee_rule_config_id": config.json()["id"]},
    )
    assert project.status_code == 200
    return config.json()["id"], project.json()["id"]


def test_unassigned_list_uses_state_category_and_displays_renamed_state(client: TestClient):
    _, project_id = _create_project(client)
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "title": f"Renamed State Task {uuid4().hex[:8]}", "owner_id": None},
    ).json()

    db = SessionLocal()
    try:
        stored = db.query(Task).filter(Task.id == task["id"]).first()
        state = db.query(WorkflowState).filter(WorkflowState.id == stored.current_state_id).first()
        renamed_state = WorkflowState(
            definition_id=state.definition_id,
            status_name="等待团队认领",
            category=state.category,
            enabled=True,
        )
        db.add(renamed_state)
        db.flush()
        stored.current_state_id = renamed_state.id
        db.commit()
    finally:
        db.close()

    response = client.get("/api/v1/work-items/unassigned")

    assert response.status_code == 200
    listed = next(item for item in response.json()["items"] if item["object_type"] == "task" and item["id"] == task["id"])
    assert listed["status"] == "等待团队认领"


def test_unassigned_list_excludes_terminal_state(client: TestClient):
    _, project_id = _create_project(client)
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "title": f"Terminal State Task {uuid4().hex[:8]}", "owner_id": None},
    ).json()

    db = SessionLocal()
    try:
        stored = db.query(Task).filter(Task.id == task["id"]).first()
        state = db.query(WorkflowState).filter(WorkflowState.id == stored.current_state_id).first()
        terminal_state = WorkflowState(
            definition_id=state.definition_id,
            status_name="测试终态",
            category="terminal",
            enabled=True,
        )
        db.add(terminal_state)
        db.flush()
        stored.current_state_id = terminal_state.id
        db.commit()
    finally:
        db.close()

    response = client.get("/api/v1/work-items/unassigned")

    assert response.status_code == 200
    assert ("task", task["id"]) not in {
        (item["object_type"], item["id"]) for item in response.json()["items"]
    }


def test_unassigned_list_contains_only_open_items_without_owner(client: TestClient):
    _, project_id = _create_project(client)
    assignee_id, _ = _create_user("Unassigned Developer", "developer")
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"Unassigned Requirement {uuid4().hex[:8]}", "owner_id": None},
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "title": f"Assigned Task {uuid4().hex[:8]}", "owner_id": assignee_id},
    ).json()
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "title": f"Unassigned Bug {uuid4().hex[:8]}", "owner_id": None},
    ).json()

    response = client.get("/api/v1/work-items/unassigned")

    assert response.status_code == 200
    keys = {(item["object_type"], item["id"]) for item in response.json()["items"]}
    assert ("requirement", requirement["id"]) in keys
    assert ("bug", bug["id"]) in keys
    assert ("task", task["id"]) not in keys
    first = next(item for item in response.json()["items"] if item["object_type"] == "requirement")
    assert first["owner_id"] is None
    assert first["waiting_hours"] >= 0
    assert "overdue" in first


def test_project_member_can_claim_unassigned_work_item(client: TestClient):
    _, project_id = _create_project(client)
    user_id, token = _create_user("Claim Developer", "developer")
    _add_project_member(project_id, user_id, "developer")
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "title": f"Claim Task {uuid4().hex[:8]}", "owner_id": None},
    ).json()

    claimed = client.post(
        f"/api/v1/workflow-runtime/task/{task['id']}/transition",
        json={"action_key": "claim"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert claimed.status_code == 200
    assert claimed.json()["owner_id"] == user_id
    assert ("task", task["id"]) not in {
        (item["object_type"], item["id"]) for item in client.get("/api/v1/work-items/unassigned").json()["items"]
    }


def test_manager_can_assign_unassigned_work_items_through_runtime(client: TestClient):
    _, project_id = _create_project(client)
    manager_id, manager_token = _create_user("Assign Manager", "project_owner")
    developer_id, _ = _create_user("Assigned Developer", "developer")
    _add_project_member(project_id, manager_id, "project_owner")
    _add_project_member(project_id, developer_id, "developer")
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"Assign Requirement {uuid4().hex[:8]}", "owner_id": None},
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "title": f"Batch Task {uuid4().hex[:8]}", "owner_id": None},
    ).json()
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "title": f"Batch Bug {uuid4().hex[:8]}", "owner_id": None},
    ).json()

    assigned = client.post(
        f"/api/v1/workflow-runtime/requirement/{requirement['id']}/transition",
        json={"action_key": "assign", "next_owner_id": developer_id, "payload": {"reason": "route to dev"}},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    task_assigned = client.post(
        f"/api/v1/workflow-runtime/task/{task['id']}/transition",
        json={"action_key": "assign", "next_owner_id": developer_id},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    bug_assigned = client.post(
        f"/api/v1/workflow-runtime/bug/{bug['id']}/transition",
        json={"action_key": "assign", "next_owner_id": developer_id},
        headers={"Authorization": f"Bearer {manager_token}"},
    )

    assert assigned.status_code == 200
    assert assigned.json()["owner_id"] == developer_id
    assert task_assigned.status_code == 200
    assert task_assigned.json()["owner_id"] == developer_id
    assert bug_assigned.status_code == 200
    assert bug_assigned.json()["owner_id"] == developer_id


def test_unassigned_list_is_scoped_to_project_members_and_system_admin(client: TestClient):
    _, project_id = _create_project(client)
    member_id, member_token = _create_user("Unassigned Queue Member", "developer")
    _, outsider_token = _create_user("Unassigned Queue Outsider", "developer")
    _, admin_token = _create_user("Unassigned Queue Admin", "system_admin")
    _add_project_member(project_id, member_id, "developer")
    task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "title": f"Scoped Unassigned Task {uuid4().hex[:8]}",
            "task_type": "standalone_operation",
            "owner_id": None,
        },
    ).json()

    member_items = client.get(
        "/api/v1/work-items/unassigned",
        headers={"Authorization": f"Bearer {member_token}"},
    ).json()["items"]
    outsider_items = client.get(
        "/api/v1/work-items/unassigned",
        headers={"Authorization": f"Bearer {outsider_token}"},
    ).json()["items"]
    admin_items = client.get(
        "/api/v1/work-items/unassigned",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()["items"]
    unauthenticated = client.get(
        "/api/v1/work-items/unassigned",
        headers={"X-Test-No-Auth": "1"},
    )
    task_ref = ("task", task["id"])

    assert task_ref in {(item["object_type"], item["id"]) for item in member_items}
    assert task_ref not in {(item["object_type"], item["id"]) for item in outsider_items}
    assert task_ref in {(item["object_type"], item["id"]) for item in admin_items}
    assert unauthenticated.status_code == 401
