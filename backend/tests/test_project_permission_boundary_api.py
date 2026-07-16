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
            username=f"perm_{uuid4().hex[:8]}",
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


def _add_project_member(project_id: int, user_id: int, project_role: str = "developer") -> None:
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


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_project_member_cannot_manage_project_configuration_or_members(client: TestClient):
    owner_id, owner_token = _create_user("Permission Project Owner")
    member_id, member_token = _create_user("Permission Project Member")
    project = client.post("/api/v1/projects", json={"name": f"Permission Project {uuid4().hex[:8]}", "owner_id": owner_id}).json()
    _add_project_member(project["id"], member_id, "developer")

    rejected_project_update = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"description": "member should not edit project"},
        headers=_auth(member_token),
    )
    rejected_member_update = client.put(
        f"/api/v1/projects/{project['id']}/members",
        json=[{"user_id": member_id, "project_role": "tech_lead", "sort_order": 0}],
        headers=_auth(member_token),
    )
    owner_project_update = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"description": "owner can edit project"},
        headers=_auth(owner_token),
    )
    owner_member_update = client.put(
        f"/api/v1/projects/{project['id']}/members",
        json=[{"user_id": member_id, "project_role": "developer", "sort_order": 0}],
        headers=_auth(owner_token),
    )

    assert rejected_project_update.status_code == 403
    assert rejected_member_update.status_code == 403
    assert owner_project_update.status_code == 200
    assert owner_member_update.status_code == 200


def test_only_system_admin_can_delete_project(client: TestClient):
    owner_id, owner_token = _create_user("Permission Delete Owner")
    admin_id, admin_token = _create_user("Permission System Admin", "system_admin")
    project = client.post("/api/v1/projects", json={"name": f"Delete Project {uuid4().hex[:8]}", "owner_id": owner_id}).json()
    admin_project = client.post("/api/v1/projects", json={"name": f"Admin Delete Project {uuid4().hex[:8]}"}).json()

    owner_delete = client.delete(f"/api/v1/projects/{project['id']}", headers=_auth(owner_token))
    admin_delete = client.delete(f"/api/v1/projects/{admin_project['id']}", headers=_auth(admin_token))

    assert owner_delete.status_code == 403
    assert admin_delete.status_code == 204
    assert client.get(f"/api/v1/projects/{project['id']}").status_code == 200
    assert client.get(f"/api/v1/projects/{admin_project['id']}").status_code == 404
    assert admin_id


def test_only_project_owner_can_create_iteration(client: TestClient):
    owner_id, owner_token = _create_user("Permission Iteration Owner")
    member_id, member_token = _create_user("Permission Iteration Member")
    project = client.post("/api/v1/projects", json={"name": f"Iteration Project {uuid4().hex[:8]}", "owner_id": owner_id}).json()
    _add_project_member(project["id"], member_id, "developer")

    rejected = client.post(
        "/api/v1/iterations",
        json={"project_id": project["id"], "name": f"Rejected Iteration {uuid4().hex[:8]}"},
        headers=_auth(member_token),
    )
    created = client.post(
        "/api/v1/iterations",
        json={"project_id": project["id"], "name": f"Allowed Iteration {uuid4().hex[:8]}"},
        headers=_auth(owner_token),
    )

    assert rejected.status_code == 403
    assert created.status_code == 200


def test_project_member_cannot_change_project_lifecycle(client: TestClient):
    owner_id, owner_token = _create_user("Permission Lifecycle Owner")
    member_id, member_token = _create_user("Permission Lifecycle Member")
    project = client.post("/api/v1/projects", json={"name": f"Lifecycle Project {uuid4().hex[:8]}", "owner_id": owner_id}).json()
    _add_project_member(project["id"], member_id, "developer")

    rejected = client.post(
        f"/api/v1/projects/{project['id']}/start",
        json={"effective_time": "2026-07-07T09:00:00"},
        headers=_auth(member_token),
    )
    allowed = client.post(
        f"/api/v1/projects/{project['id']}/start",
        json={"effective_time": "2026-07-07T09:00:00"},
        headers=_auth(owner_token),
    )

    assert rejected.status_code == 403
    assert allowed.status_code == 200


def test_work_item_create_requires_project_member_and_login(client: TestClient):
    owner_id, _ = _create_user("Permission Create Owner")
    member_id, member_token = _create_user("Permission Create Member")
    outsider_id, outsider_token = _create_user("Permission Create Outsider")
    project = client.post("/api/v1/projects", json={"name": f"Create Project {uuid4().hex[:8]}", "owner_id": owner_id}).json()
    _add_project_member(project["id"], member_id, "developer")

    unauthenticated = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "title": f"Unauth Req {uuid4().hex[:8]}", "owner_id": member_id},
        headers={"X-Test-No-Auth": "1"},
    )
    rejected = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "title": f"Rejected Req {uuid4().hex[:8]}", "owner_id": outsider_id},
        headers=_auth(outsider_token),
    )
    allowed = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "title": f"Allowed Req {uuid4().hex[:8]}", "owner_id": member_id},
        headers=_auth(member_token),
    )

    assert unauthenticated.status_code == 401
    assert rejected.status_code == 403
    assert allowed.status_code == 200


def test_only_project_owner_can_delete_work_item(client: TestClient):
    owner_id, owner_token = _create_user("Permission Delete Work Owner")
    member_id, member_token = _create_user("Permission Delete Work Member")
    project = client.post("/api/v1/projects", json={"name": f"Delete Work Project {uuid4().hex[:8]}", "owner_id": owner_id}).json()
    _add_project_member(project["id"], member_id, "developer")
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "title": f"Deletable Task {uuid4().hex[:8]}", "owner_id": member_id},
        headers=_auth(member_token),
    ).json()

    rejected = client.delete(f"/api/v1/tasks/{task['id']}", headers=_auth(member_token))
    allowed = client.delete(f"/api/v1/tasks/{task['id']}", headers=_auth(owner_token))

    assert rejected.status_code == 403
    assert allowed.status_code == 204


def test_test_case_manage_and_execute_requires_test_role(client: TestClient):
    owner_id, _ = _create_user("Permission Test Owner")
    developer_id, developer_token = _create_user("Permission Test Developer")
    tester_id, tester_token = _create_user("Permission Test Tester")
    project = client.post("/api/v1/projects", json={"name": f"Test Case Project {uuid4().hex[:8]}", "owner_id": owner_id}).json()
    _add_project_member(project["id"], developer_id, "developer")
    _add_project_member(project["id"], tester_id, "tester")

    rejected_create = client.post(
        "/api/v1/test-cases",
        json={"project_id": project["id"], "title": f"Rejected Case {uuid4().hex[:8]}"},
        headers=_auth(developer_token),
    )
    created = client.post(
        "/api/v1/test-cases",
        json={"project_id": project["id"], "title": f"Allowed Case {uuid4().hex[:8]}"},
        headers=_auth(tester_token),
    )
    rejected_execution = client.post(
        f"/api/v1/test-cases/{created.json()['id']}/executions",
        json={"steps_result_json": {"result": "passed"}},
        headers=_auth(developer_token),
    )
    allowed_execution = client.post(
        f"/api/v1/test-cases/{created.json()['id']}/executions",
        json={"steps_result_json": {"result": "passed"}},
        headers=_auth(tester_token),
    )

    assert rejected_create.status_code == 403
    assert created.status_code == 200
    assert rejected_execution.status_code == 403
    assert allowed_execution.status_code == 200


def test_only_system_admin_can_modify_workflow_configuration(client: TestClient):
    user_id, user_token = _create_user("Permission Workflow User")
    admin_id, admin_token = _create_user("Permission Workflow Admin", "system_admin")

    rejected = client.post(
        "/api/v1/assignee-rule-configs",
        json={"name": f"Rejected Scheme {uuid4().hex[:8]}"},
        headers=_auth(user_token),
    )
    allowed = client.post(
        "/api/v1/assignee-rule-configs",
        json={"name": f"Allowed Scheme {uuid4().hex[:8]}"},
        headers=_auth(admin_token),
    )

    assert rejected.status_code == 403
    assert allowed.status_code == 201
    assert user_id and admin_id


def test_project_owner_can_admin_edit_non_current_handler_work_item(client: TestClient):
    owner_id, owner_token = _create_user("Permission Work Item Owner")
    handler_id, handler_token = _create_user("Permission Current Handler")
    member_id, member_token = _create_user("Permission Other Member")
    project = client.post("/api/v1/projects", json={"name": f"Work Item Project {uuid4().hex[:8]}", "owner_id": owner_id}).json()
    _add_project_member(project["id"], handler_id, "developer")
    _add_project_member(project["id"], member_id, "developer")
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "title": f"Permission Task {uuid4().hex[:8]}", "owner_id": handler_id},
        headers=_auth(handler_token),
    ).json()

    rejected = client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"description": "other member cannot edit"},
        headers=_auth(member_token),
    )
    owner_edit = client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"description": "project owner can admin edit"},
        headers=_auth(owner_token),
    )
    handler_edit = client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"description": "handler can edit"},
        headers=_auth(handler_token),
    )

    assert rejected.status_code == 403
    assert owner_edit.status_code == 200
    assert handler_edit.status_code == 200


def test_generic_patch_rejects_owner_and_status_changes(client: TestClient):
    project_owner_id, _ = _create_user("Protected Patch Project Owner")
    handler_id, handler_token = _create_user("Protected Patch Handler")
    target_id, _ = _create_user("Protected Patch Target")
    project = client.post(
        "/api/v1/projects",
        json={"name": f"Protected Patch Project {uuid4().hex[:8]}", "owner_id": project_owner_id},
    ).json()
    _add_project_member(project["id"], handler_id, "developer")
    _add_project_member(project["id"], target_id, "developer")

    objects = [
        (
            "requirements",
            client.post(
                "/api/v1/requirements",
                json={"project_id": project["id"], "title": f"Protected Requirement {uuid4().hex[:8]}", "owner_id": handler_id},
            ).json(),
            "completed",
        ),
        (
            "tasks",
            client.post(
                "/api/v1/tasks",
                json={
                    "project_id": project["id"],
                    "title": f"Protected Task {uuid4().hex[:8]}",
                    "task_type": "standalone_operation",
                    "owner_id": handler_id,
                },
            ).json(),
            "completed",
        ),
        (
            "bugs",
            client.post(
                "/api/v1/bugs",
                json={"project_id": project["id"], "title": f"Protected Bug {uuid4().hex[:8]}", "owner_id": handler_id},
            ).json(),
            "closed",
        ),
    ]

    for endpoint, item, target_status in objects:
        response = client.patch(
            f"/api/v1/{endpoint}/{item['id']}",
            json={"owner_id": target_id, "status": target_status},
            headers=_auth(handler_token),
        )
        unchanged = client.get(f"/api/v1/{endpoint}/{item['id']}").json()

        assert response.status_code == 422
        assert unchanged["owner_id"] == handler_id
        assert unchanged["current_state_id"] == item["current_state_id"]
