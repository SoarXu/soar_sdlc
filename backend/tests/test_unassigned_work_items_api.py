from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.session import SessionLocal
from app.models.project_member import ProjectMember
from app.models.role import Role, UserRole
from app.models.user import User


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
        },
    )
    assert config.status_code == 201
    project = client.post(
        "/api/v1/projects",
        json={"name": f"Work Item Project {uuid4().hex[:8]}", "assignee_rule_config_id": config.json()["id"]},
    )
    assert project.status_code == 200
    return config.json()["id"], project.json()["id"]


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
        f"/api/v1/work-items/task/{task['id']}/claim",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert claimed.status_code == 200
    assert claimed.json()["owner_id"] == user_id
    assert ("task", task["id"]) not in {
        (item["object_type"], item["id"]) for item in client.get("/api/v1/work-items/unassigned").json()["items"]
    }


def test_manager_can_assign_and_batch_assign_work_items(client: TestClient):
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
        f"/api/v1/work-items/requirement/{requirement['id']}/assign",
        json={"owner_id": developer_id, "remark": "route to dev"},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    batch = client.post(
        "/api/v1/work-items/batch-assign",
        json={
            "items": [
                {"object_type": "task", "id": task["id"]},
                {"object_type": "bug", "id": bug["id"]},
            ],
            "owner_id": developer_id,
        },
        headers={"Authorization": f"Bearer {manager_token}"},
    )

    assert assigned.status_code == 200
    assert assigned.json()["owner_id"] == developer_id
    assert batch.status_code == 200
    assert {(item["object_type"], item["id"]) for item in batch.json()["success_items"]} == {
        ("task", task["id"]),
        ("bug", bug["id"]),
    }
    assert batch.json()["failures"] == []


def test_auto_assign_unassigned_items_uses_visual_workflow_transition_rule(client: TestClient):
    config_id, project_id = _create_project(client)
    manager_id, manager_token = _create_user("Auto Assign Manager", "project_owner")
    developer_id, _ = _create_user("Auto Developer", "developer")
    _add_project_member(project_id, manager_id, "project_owner")
    _add_project_member(project_id, developer_id, "developer")
    definition = client.post(
        "/api/v1/workflow-definitions",
        json={
            "name": f"Auto Assign Workflow {uuid4().hex[:8]}",
            "object_type": "bug",
            "scope_type": "assignee_rule_config",
            "scope_id": config_id,
        },
    )
    assert definition.status_code == 201
    graph = client.put(
        f"/api/v1/workflow-definitions/{definition.json()['id']}/graph",
        json={
            "states": [
                {"status_key": "open", "status_name": "Open", "category": "start", "x": 100, "y": 100},
                {"status_key": "fixing", "status_name": "Fixing", "category": "normal", "x": 280, "y": 100},
            ],
            "transitions": [
                {
                    "action_key": "start_fixing",
                    "action_name": "Start fixing",
                    "from_status": "open",
                    "to_status": "fixing",
                    "handler_rule": {
                        "target_type": "project_role",
                        "target_roles": "developer",
                        "fallback_type": "none",
                    },
                }
            ],
        },
    )
    assert graph.status_code == 200
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "title": f"Auto Assign Bug {uuid4().hex[:8]}", "owner_id": None},
    ).json()

    result = client.post(
        "/api/v1/work-items/unassigned/auto-assign",
        json={"items": [{"object_type": "bug", "id": bug["id"]}]},
        headers={"Authorization": f"Bearer {manager_token}"},
    )

    assert result.status_code == 200
    assert result.json()["success_items"] == [{"object_type": "bug", "id": bug["id"], "owner_id": developer_id}]
    assert result.json()["failures"] == []
