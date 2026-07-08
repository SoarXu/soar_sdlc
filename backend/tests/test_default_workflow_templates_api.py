from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.session import SessionLocal
from app.models.bug import Bug
from app.models.iteration import Iteration
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.requirement import Requirement
from app.models.role import Role, UserRole
from app.models.task import Task
from app.models.user import User


def _create_user(full_name: str, role_key: str) -> tuple[int, str]:
    db = SessionLocal()
    try:
        user = User(
            username=f"default_template_{uuid4().hex[:8]}",
            full_name=full_name,
            password_hash=get_password_hash("User123456"),
            is_active=True,
        )
        db.add(user)
        db.flush()
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


def _create_project_with_config(client: TestClient) -> int:
    config = client.post(
        "/api/v1/assignee-rule-configs",
        json={
            "name": f"Default Template Config {uuid4().hex[:8]}",
            "requirement_owner_roles": "product_owner",
            "task_owner_roles": "developer",
            "test_case_tester_roles": "tester",
            "test_run_owner_roles": "tester",
            "bug_owner_roles": "developer",
        },
    )
    assert config.status_code == 201
    project = client.post(
        "/api/v1/projects",
        json={"name": f"Default Template Project {uuid4().hex[:8]}", "assignee_rule_config_id": config.json()["id"]},
    )
    assert project.status_code == 200
    return project.json()["id"]


def _set_requirement_status(requirement_id: int, status: str) -> None:
    db = SessionLocal()
    try:
        requirement = db.query(Requirement).filter(Requirement.id == requirement_id).first()
        assert requirement is not None
        requirement.status = status
        db.commit()
    finally:
        db.close()


def _set_task_status(task_id: int, status: str) -> None:
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        assert task is not None
        task.status = status
        db.commit()
    finally:
        db.close()


def _set_bug_status(bug_id: int, status: str) -> None:
    db = SessionLocal()
    try:
        bug = db.query(Bug).filter(Bug.id == bug_id).first()
        assert bug is not None
        bug.status = status
        db.commit()
    finally:
        db.close()


def _set_iteration_status(iteration_id: int, status: str) -> None:
    db = SessionLocal()
    try:
        iteration = db.query(Iteration).filter(Iteration.id == iteration_id).first()
        assert iteration is not None
        iteration.status = status
        db.commit()
    finally:
        db.close()


def _set_project_status(project_id: int, status: str) -> None:
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        assert project is not None
        project.status = status
        db.commit()
    finally:
        db.close()


def test_bug_defaults_to_pending_handling_and_close_blocks_on_direct_task(client: TestClient):
    project_id = _create_project_with_config(client)
    handler_id, handler_token = _create_user("Default Template Developer", "developer")
    _add_project_member(project_id, handler_id, "developer")
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "title": f"Linked task {uuid4().hex[:8]}", "owner_id": handler_id},
    ).json()
    bug = client.post(
        "/api/v1/bugs",
        json={
            "project_id": project_id,
            "task_id": task["id"],
            "title": f"Linked bug {uuid4().hex[:8]}",
            "owner_id": handler_id,
        },
    )

    assert bug.status_code == 200
    assert bug.json()["status"] == "pending_handling"

    _set_bug_status(bug.json()["id"], "verified")
    close = client.post(
        f"/api/v1/workflow-runtime/bug/{bug.json()['id']}/transition",
        json={"action_key": "close", "payload": {"reason": "verified done"}},
        headers={"Authorization": f"Bearer {handler_token}"},
    )

    assert close.status_code == 400
    assert "task" in close.json()["detail"].lower()


def test_task_branch_defaults_follow_confirmation_template(client: TestClient):
    project_id = _create_project_with_config(client)
    handler_id, handler_token = _create_user("Task Branch Developer", "developer")
    _add_project_member(project_id, handler_id, "developer")

    bug_fix_task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "title": f"Bug fix task {uuid4().hex[:8]}",
            "task_type": "bug_fix",
            "owner_id": handler_id,
        },
    )
    requirement_task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "title": f"Requirement task {uuid4().hex[:8]}",
            "task_type": "requirement_implementation",
            "owner_id": handler_id,
        },
    )
    unassigned_task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "title": f"Standalone task {uuid4().hex[:8]}",
            "task_type": "standalone_operation",
        },
    )

    assert bug_fix_task.status_code == 200
    assert bug_fix_task.json()["status"] == "in_processing"
    assert requirement_task.status_code == 200
    assert requirement_task.json()["status"] == "in_processing"
    assert unassigned_task.status_code == 200
    assert unassigned_task.json()["status"] == "pending_assignment"

    bug_fix_actions = client.get(
        f"/api/v1/workflow-runtime/task/{bug_fix_task.json()['id']}/transitions",
        headers={"Authorization": f"Bearer {handler_token}"},
    )
    requirement_actions = client.get(
        f"/api/v1/workflow-runtime/task/{requirement_task.json()['id']}/transitions",
        headers={"Authorization": f"Bearer {handler_token}"},
    )

    assert bug_fix_actions.status_code == 200
    assert "submit_confirmation" in {item["action_key"] for item in bug_fix_actions.json()}
    assert "complete" not in {item["action_key"] for item in bug_fix_actions.json()}
    assert requirement_actions.status_code == 200
    assert "complete" in {item["action_key"] for item in requirement_actions.json()}


def test_requirement_complete_and_cancel_block_on_direct_relations(client: TestClient):
    project_id = _create_project_with_config(client)
    handler_id, handler_token = _create_user("Requirement Handler", "developer")
    _add_project_member(project_id, handler_id, "developer")
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"Requirement {uuid4().hex[:8]}", "owner_id": handler_id},
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "requirement_id": requirement["id"],
            "title": f"Requirement task {uuid4().hex[:8]}",
            "owner_id": handler_id,
        },
    ).json()
    bug = client.post(
        "/api/v1/bugs",
        json={
            "project_id": project_id,
            "requirement_id": requirement["id"],
            "title": f"Requirement bug {uuid4().hex[:8]}",
            "owner_id": handler_id,
        },
    ).json()
    _set_requirement_status(requirement["id"], "in_processing")
    _set_task_status(task["id"], "completed")
    _set_bug_status(bug["id"], "pending_verification")

    complete = client.post(
        f"/api/v1/workflow-runtime/requirement/{requirement['id']}/transition",
        json={"action_key": "complete", "payload": {}},
        headers={"Authorization": f"Bearer {handler_token}"},
    )

    assert complete.status_code == 400
    assert "bug" in complete.json()["detail"].lower()

    _set_bug_status(bug["id"], "closed")
    _set_task_status(task["id"], "in_processing")
    cancel = client.post(
        f"/api/v1/workflow-runtime/requirement/{requirement['id']}/transition",
        json={"action_key": "cancel", "payload": {"reason": "scope removed"}},
        headers={"Authorization": f"Bearer {handler_token}"},
    )

    assert cancel.status_code == 400
    assert "task" in cancel.json()["detail"].lower()


def test_iteration_complete_and_cancel_block_on_direct_items(client: TestClient):
    project_id = _create_project_with_config(client)
    handler_id, handler_token = _create_user("Iteration Handler", "project_owner")
    _add_project_member(project_id, handler_id, "project_owner")
    iteration = client.post(
        "/api/v1/iterations",
        json={"project_ids": [project_id], "name": f"Iteration {uuid4().hex[:8]}"},
    ).json()
    client.post(
        "/api/v1/requirements",
        json={
            "project_id": project_id,
            "iteration_id": iteration["id"],
            "title": f"Iteration requirement {uuid4().hex[:8]}",
            "owner_id": handler_id,
        },
    )
    client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "iteration_id": iteration["id"],
            "title": f"Iteration task {uuid4().hex[:8]}",
            "owner_id": handler_id,
        },
    )
    client.post(
        "/api/v1/bugs",
        json={
            "project_id": project_id,
            "iteration_id": iteration["id"],
            "title": f"Iteration bug {uuid4().hex[:8]}",
            "owner_id": handler_id,
        },
    )
    _set_iteration_status(iteration["id"], "active")

    complete = client.post(
        f"/api/v1/workflow-runtime/iteration/{iteration['id']}/transition",
        json={"action_key": "complete", "payload": {}},
        headers={"Authorization": f"Bearer {handler_token}"},
    )
    cancel = client.post(
        f"/api/v1/workflow-runtime/iteration/{iteration['id']}/transition",
        json={"action_key": "cancel", "payload": {"reason": "stop iteration"}},
        headers={"Authorization": f"Bearer {handler_token}"},
    )

    assert complete.status_code == 400
    assert "requirement" in complete.json()["detail"].lower() or "bug" in complete.json()["detail"].lower()
    assert cancel.status_code == 400
    assert "task" in cancel.json()["detail"].lower() or "bug" in cancel.json()["detail"].lower()


def test_project_close_blocks_on_direct_scoped_objects(client: TestClient):
    project_id = _create_project_with_config(client)
    handler_id, handler_token = _create_user("Project Owner", "project_owner")
    _add_project_member(project_id, handler_id, "project_owner")
    iteration = client.post(
        "/api/v1/iterations",
        json={"project_ids": [project_id], "name": f"Project iteration {uuid4().hex[:8]}"},
    ).json()
    client.post(
        "/api/v1/bugs",
        json={
            "project_id": project_id,
            "iteration_id": iteration["id"],
            "title": f"Project bug {uuid4().hex[:8]}",
            "owner_id": handler_id,
        },
    )
    _set_project_status(project_id, "active")

    close = client.post(
        f"/api/v1/workflow-runtime/project/{project_id}/transition",
        json={"action_key": "close", "payload": {"reason": "release done"}},
        headers={"Authorization": f"Bearer {handler_token}"},
    )

    assert close.status_code == 400
    assert "bug" in close.json()["detail"].lower() or "iteration" in close.json()["detail"].lower()
