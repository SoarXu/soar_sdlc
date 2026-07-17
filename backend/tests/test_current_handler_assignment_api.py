from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.session import SessionLocal
from app.models.project_member import ProjectMember
from app.models.requirement import Requirement
from app.models.role import Role, UserRole
from app.models.task import Task
from app.models.user import User
from app.models.workflow_definition import WorkflowState, WorkflowTransition


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


def _set_requirement_status(requirement_id: int, status: str) -> None:
    db = SessionLocal()
    try:
        requirement = db.query(Requirement).filter(Requirement.id == requirement_id).one()
        requirement.current_state_id = _state_id(db, requirement.workflow_definition_id, status)
        db.commit()
    finally:
        db.close()


def _set_task_status(task_id: int, status: str) -> None:
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).one()
        task.current_state_id = _state_id(db, task.workflow_definition_id, status)
        db.commit()
    finally:
        db.close()


def _state_id(db, definition_id: int, status: str) -> int:
    action_key = {"completed": "complete", "canceled": "cancel"}[status]
    state_ids = {
        value
        for value, in db.query(WorkflowTransition.to_state_id).filter(
            WorkflowTransition.definition_id == definition_id,
            WorkflowTransition.action_key == action_key,
        ).all()
    }
    assert len(state_ids) == 1
    return next(iter(state_ids))


def _runtime_transition(
    client: TestClient,
    object_type: str,
    object_id: int,
    action_key: str,
    token: str,
    payload: dict | None = None,
):
    return client.post(
        f"/api/v1/workflow-runtime/{object_type}/{object_id}/transition",
        json={"action_key": action_key, "payload": payload or {}},
        headers={"Authorization": f"Bearer {token}"},
    )


def test_create_work_items_do_not_use_default_owner_roles(client: TestClient):
    developer_id, _ = _create_user("Default Role Developer", "developer")
    config = client.post(
        "/api/v1/assignee-rule-configs",
        json={
            "name": f"Ownerless Config-{uuid4().hex[:8]}",
            "requirement_owner_roles": "developer",
            "task_owner_roles": "developer",
            "bug_owner_roles": "developer",
            "creation_mode": "template",
            "template_source": {"source_type": "system", "source_id": "system-standard"},
        },
    )
    assert config.status_code == 201
    enabled = client.post(f"/api/v1/assignee-rule-configs/{config.json()['id']}/enable")
    assert enabled.status_code == 200, enabled.text
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


def test_requirement_change_handler_updates_current_handler_and_records_history(client: TestClient):
    owner_id, owner_token = _create_user("Original Handler", "developer")
    target_id, _ = _create_user("Target Handler", "developer")
    manager_id, manager_token = _create_user("Project Manager", "project_owner")
    project_id = _create_project(client, owner_id=manager_id)
    _add_project_member(project_id, owner_id)
    _add_project_member(project_id, target_id)
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"Assignable requirement-{uuid4().hex[:8]}", "owner_id": owner_id},
    ).json()
    claimed = _runtime_transition(client, "requirement", requirement["id"], "claim", owner_token)
    assert claimed.status_code == 200, claimed.text

    assigned = client.post(
        f"/api/v1/workflow-runtime/requirement/{requirement['id']}/transition",
        json={
            "action_key": "change_handler",
            "next_owner_id": target_id,
            "delegate_reason": "管理调整",
            "payload": {"reason": "转给目标处理"},
        },
        headers={"Authorization": f"Bearer {manager_token}"},
    )

    assert assigned.status_code == 200
    assert assigned.json()["owner_id"] == target_id
    history = client.get(f"/api/v1/requirements/{requirement['id']}/status-operations").json()
    assert history[-1]["action"] == "change_handler"
    assert history[-1]["from_state_name"] == "处理中"
    assert history[-1]["to_state_name"] == "处理中"
    assert history[-1]["actor_id"] == manager_id
    assert f"{owner_id} -> {target_id}" in history[-1]["remark"]
    assert history[-1]["reason"] == "转给目标处理"


def test_project_owner_is_not_implicit_current_handler_assignee(client: TestClient):
    owner_id, owner_token = _create_user("Management Owner", "project_owner")
    project_id = _create_project(client, owner_id=owner_id)
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"Project owner is management only-{uuid4().hex[:8]}"},
    ).json()

    assigned = client.post(
        f"/api/v1/workflow-runtime/requirement/{requirement['id']}/transition",
        json={"action_key": "assign", "next_owner_id": owner_id, "payload": {"reason": "try assign to project owner"}},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert assigned.status_code == 400
    assert "not a project member" in assigned.json()["detail"].lower()


def test_runtime_change_handler_rejects_terminal_items_independently(client: TestClient):
    owner_id, owner_token = _create_user("Batch Owner", "developer")
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
    claimed = _runtime_transition(client, "requirement", active_requirement["id"], "claim", owner_token)
    assert claimed.status_code == 200, claimed.text
    _set_requirement_status(closed_requirement["id"], "canceled")

    active_response = client.post(
        f"/api/v1/workflow-runtime/requirement/{active_requirement['id']}/transition",
        json={
            "action_key": "change_handler",
            "next_owner_id": target_id,
            "delegate_reason": "管理调整",
            "payload": {"reason": "转派"},
        },
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    terminal_response = client.post(
        f"/api/v1/workflow-runtime/requirement/{closed_requirement['id']}/transition",
        json={
            "action_key": "change_handler",
            "next_owner_id": target_id,
            "delegate_reason": "管理调整",
            "payload": {"reason": "不应转派"},
        },
        headers={"Authorization": f"Bearer {manager_token}"},
    )

    assert active_response.status_code == 200
    assert terminal_response.status_code == 400
    assert client.get(f"/api/v1/requirements/{active_requirement['id']}").json()["owner_id"] == target_id


def test_non_current_handler_cannot_update_or_transition_task(client: TestClient):
    owner_id, owner_token = _create_user("Task Handler", "developer")
    other_id, other_token = _create_user("Other Developer", "developer")
    project_id = _create_project(client)
    _add_project_member(project_id, owner_id)
    _add_project_member(project_id, other_id)
    task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "title": f"Protected task-{uuid4().hex[:8]}",
            "task_type": "requirement_implementation",
            "owner_id": owner_id,
        },
    ).json()
    claimed = _runtime_transition(client, "task", task["id"], "claim", owner_token)
    assert claimed.status_code == 200, claimed.text

    rejected_update = client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"title": "Should not update"},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    rejected_transition = _runtime_transition(client, "task", task["id"], "complete", other_token)
    accepted_transition = _runtime_transition(client, "task", task["id"], "complete", owner_token)

    assert rejected_update.status_code == 403
    assert rejected_transition.status_code == 403
    assert accepted_transition.status_code == 200


def test_workbench_defaults_to_current_users_non_terminal_items(client: TestClient):
    user_id, user_token = _create_user("Workbench Current", "developer")
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
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
            "title": "Done task",
            "task_type": "requirement_implementation",
            "owner_id": user_id,
        },
    ).json()
    _set_task_status(done_task["id"], "completed")

    response = client.get(
        "/api/v1/dashboard/workbench",
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 200
    pending_items = response.json()["pending_handling"]["items"]
    pending_refs = {(item["object_type"], item["id"]) for item in pending_items}
    assert ("requirement", my_requirement["id"]) in pending_refs
    assert ("requirement", other_requirement["id"]) not in pending_refs
    assert ("task", done_task["id"]) not in pending_refs


def test_workbench_my_queue_uses_owner_not_project_membership(client: TestClient):
    user_id, user_token = _create_user("Owner Without Membership", "developer")
    teammate_id, teammate_token = _create_user("Project Teammate", "developer")
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

    owner_response = client.get(
        "/api/v1/dashboard/workbench",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    teammate_response = client.get(
        "/api/v1/dashboard/workbench",
        headers={"Authorization": f"Bearer {teammate_token}"},
    )

    assert owner_response.status_code == 200
    owner_refs = {(item["object_type"], item["id"]) for item in owner_response.json()["pending_handling"]["items"]}
    assert ("bug", my_bug["id"]) in owner_refs
    assert ("task", teammate_task["id"]) not in owner_refs

    assert teammate_response.status_code == 200
    teammate_refs = {(item["object_type"], item["id"]) for item in teammate_response.json()["pending_handling"]["items"]}
    assert ("task", teammate_task["id"]) in teammate_refs
    assert ("bug", my_bug["id"]) not in teammate_refs


def test_legacy_owner_mutation_routes_are_removed_from_openapi(client: TestClient):
    paths = set(client.get("/openapi.json").json()["paths"])
    legacy_paths = {
        "/api/v1/requirements/batch-assign",
        "/api/v1/requirements/{requirement_id}/assign",
        "/api/v1/tasks/batch-assign",
        "/api/v1/tasks/{task_id}/assign",
        "/api/v1/bugs/batch-assign",
        "/api/v1/bugs/{bug_id}/assign",
        "/api/v1/work-items/{object_type}/{object_id}/claim",
        "/api/v1/work-items/{object_type}/{object_id}/assign",
        "/api/v1/work-items/batch-assign",
        "/api/v1/work-items/unassigned/auto-assign",
    }

    assert paths.isdisjoint(legacy_paths)
