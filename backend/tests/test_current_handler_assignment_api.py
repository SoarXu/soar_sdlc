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
            username=f"handler_{uuid4().hex[:8]}",
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


def _create_project(client: TestClient, owner_id: int | None = None) -> int:
    payload = {"name": f"Handler Project-{uuid4().hex[:8]}"}
    if owner_id:
        payload["owner_id"] = owner_id
    response = client.post("/api/v1/projects", json=payload)
    assert response.status_code == 200
    return response.json()["id"]


def _create_iteration(client: TestClient, project_id: int) -> int:
    response = client.post(
        "/api/v1/iterations",
        json={"project_ids": [project_id], "name": f"Handler Iteration-{uuid4().hex[:8]}"},
    )
    assert response.status_code == 200
    return response.json()["id"]


def _add_project_member(project_id: int, user_id: int, project_role: str = "developer") -> None:
    db = SessionLocal()
    try:
        db.add(ProjectMember(project_id=project_id, user_id=user_id, project_role=project_role, is_workbench_participant=True))
        db.commit()
    finally:
        db.close()


def test_create_work_items_do_not_use_default_owner_roles(client: TestClient):
    developer_id, _ = _create_user("Default Role Developer", "developer")
    config = client.post(
        "/api/v1/assignee-rule-configs",
        json={
            "name": f"Ownerless Config-{uuid4().hex[:8]}",
            "requirement_owner_roles": "developer",
            "task_owner_roles": "developer",
            "bug_owner_roles": "developer",
        },
    )
    assert config.status_code == 201
    project = client.post(
        "/api/v1/projects",
        json={"name": f"Ownerless Project-{uuid4().hex[:8]}", "assignee_rule_config_id": config.json()["id"]},
    ).json()
    _add_project_member(project["id"], developer_id, "developer")

    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "title": f"Ownerless requirement-{uuid4().hex[:8]}"},
    )
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "title": f"Ownerless task-{uuid4().hex[:8]}"},
    )
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project["id"], "title": f"Ownerless bug-{uuid4().hex[:8]}"},
    )

    assert requirement.status_code == 200
    assert task.status_code == 200
    assert bug.status_code == 200
    assert requirement.json()["owner_id"] is None
    assert task.json()["owner_id"] is None
    assert bug.json()["owner_id"] is None


def test_requirement_assign_updates_current_handler_and_records_history(client: TestClient):
    owner_id, _ = _create_user("Original Handler", "developer")
    target_id, _ = _create_user("Target Handler", "developer")
    manager_id, manager_token = _create_user("Project Manager", "project_owner")
    project_id = _create_project(client, owner_id=manager_id)
    _add_project_member(project_id, owner_id)
    _add_project_member(project_id, target_id)
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"Assignable requirement-{uuid4().hex[:8]}", "owner_id": owner_id},
    ).json()

    assigned = client.post(
        f"/api/v1/requirements/{requirement['id']}/assign",
        json={"owner_id": target_id, "remark": "转给目标处理"},
        headers={"Authorization": f"Bearer {manager_token}"},
    )

    assert assigned.status_code == 200
    assert assigned.json()["owner_id"] == target_id
    history = client.get(f"/api/v1/requirements/{requirement['id']}/status-operations").json()
    assert history[-1]["action"] == "assign"
    assert history[-1]["from_status"] == requirement["status"]
    assert history[-1]["to_status"] == requirement["status"]
    assert history[-1]["actor_id"] == manager_id
    assert f"{owner_id} -> {target_id}" in history[-1]["remark"]
    assert "转给目标处理" in history[-1]["remark"]


def test_project_owner_is_not_implicit_current_handler_assignee(client: TestClient):
    owner_id, owner_token = _create_user("Management Owner", "project_owner")
    project_id = _create_project(client, owner_id=owner_id)
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"Project owner is management only-{uuid4().hex[:8]}"},
    ).json()

    assigned = client.post(
        f"/api/v1/requirements/{requirement['id']}/assign",
        json={"owner_id": owner_id, "remark": "try assign to project owner"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert assigned.status_code == 400
    assert "不是对象所属项目成员" in assigned.json()["detail"]


def test_batch_assign_returns_success_and_failure_items(client: TestClient):
    owner_id, _ = _create_user("Batch Owner", "developer")
    target_id, _ = _create_user("Batch Target", "developer")
    manager_id, manager_token = _create_user("Batch Manager", "project_owner")
    project_id = _create_project(client, owner_id=manager_id)
    _add_project_member(project_id, owner_id)
    _add_project_member(project_id, target_id)
    active_requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"Batch active-{uuid4().hex[:8]}", "owner_id": owner_id},
    ).json()
    closed_requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"Batch closed-{uuid4().hex[:8]}", "owner_id": owner_id},
    ).json()
    client.post(f"/api/v1/requirements/{closed_requirement['id']}/activate")
    client.post(f"/api/v1/requirements/{closed_requirement['id']}/close", json={"reason": "不做"})

    response = client.post(
        "/api/v1/requirements/batch-assign",
        json={"ids": [active_requirement["id"], closed_requirement["id"]], "owner_id": target_id, "remark": "批量转派"},
        headers={"Authorization": f"Bearer {manager_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success_ids"] == [active_requirement["id"]]
    assert data["failures"][0]["id"] == closed_requirement["id"]
    assert "已完成或已关闭" in data["failures"][0]["reason"]
    assert client.get(f"/api/v1/requirements/{active_requirement['id']}").json()["owner_id"] == target_id


def test_non_current_handler_cannot_update_or_transition_task(client: TestClient):
    owner_id, owner_token = _create_user("Task Handler", "developer")
    other_id, other_token = _create_user("Other Developer", "developer")
    project_id = _create_project(client)
    _add_project_member(project_id, owner_id)
    _add_project_member(project_id, other_id)
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "title": f"Protected task-{uuid4().hex[:8]}", "owner_id": owner_id},
    ).json()

    rejected_update = client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"title": "Should not update"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    rejected_transition = client.post(
        f"/api/v1/tasks/{task['id']}/activate",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    accepted_transition = client.post(
        f"/api/v1/tasks/{task['id']}/activate",
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert rejected_update.status_code == 403
    assert rejected_transition.status_code == 403
    assert accepted_transition.status_code == 200


def test_workbench_defaults_to_current_users_non_terminal_items(client: TestClient):
    user_id, _ = _create_user("Workbench Current", "developer")
    other_id, _ = _create_user("Workbench Other", "developer")
    project_id = _create_project(client)
    iteration_id = _create_iteration(client, project_id)
    _add_project_member(project_id, user_id)
    _add_project_member(project_id, other_id)
    my_requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": "My requirement", "owner_id": user_id},
    ).json()
    other_requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": "Other requirement", "owner_id": other_id},
    ).json()
    done_task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": "Done task", "owner_id": user_id},
    ).json()
    client.post(f"/api/v1/tasks/{done_task['id']}/activate")
    client.post(f"/api/v1/tasks/{done_task['id']}/complete")

    response = client.get(f"/api/v1/dashboard/workbench?user_id={user_id}")

    assert response.status_code == 200
    board = next(item for item in response.json()["iterations"] if item["id"] == iteration_id)
    assert {item["id"] for item in board["requirements"]} == {my_requirement["id"]}
    assert other_requirement["id"] not in {item["id"] for item in board["requirements"]}
    assert done_task["id"] not in {item["id"] for item in board["tasks"]}


def test_workbench_my_queue_uses_owner_not_project_membership(client: TestClient):
    user_id, _ = _create_user("Owner Without Membership", "developer")
    teammate_id, _ = _create_user("Project Teammate", "developer")
    project_id = _create_project(client)
    iteration_id = _create_iteration(client, project_id)
    _add_project_member(project_id, teammate_id)
    my_bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": "Assigned to outsider", "owner_id": user_id},
    ).json()
    teammate_task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": "Assigned to project member", "owner_id": teammate_id},
    ).json()

    owner_response = client.get(f"/api/v1/dashboard/workbench?user_id={user_id}")
    teammate_response = client.get(f"/api/v1/dashboard/workbench?user_id={teammate_id}")

    assert owner_response.status_code == 200
    owner_board = next(item for item in owner_response.json()["iterations"] if item["id"] == iteration_id)
    assert {item["id"] for item in owner_board["bugs"]} == {my_bug["id"]}
    assert teammate_task["id"] not in {item["id"] for item in owner_board["tasks"]}

    assert teammate_response.status_code == 200
    teammate_board = next(item for item in teammate_response.json()["iterations"] if item["id"] == iteration_id)
    assert {item["id"] for item in teammate_board["tasks"]} == {teammate_task["id"]}
    assert my_bug["id"] not in {item["id"] for item in teammate_board["bugs"]}
