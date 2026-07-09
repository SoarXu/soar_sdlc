from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.session import SessionLocal
from app.models.project_member import ProjectMember
from app.models.role import Role, UserRole
from app.models.test_case import TestCase
from app.models.user import User


def _create_actor_token(full_name: str, role_key: str = "developer") -> tuple[str, int]:
    db = SessionLocal()
    try:
        user = User(
            username=f"actor.{uuid4().hex[:8]}",
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
        return create_access_token(user.username), user.id
    finally:
        db.close()


def _create_project(client: TestClient) -> int:
    response = client.post("/api/v1/projects", json={"name": f"项目-{uuid4().hex[:8]}"})
    assert response.status_code == 200
    return response.json()["id"]


def _create_named_project(client: TestClient, name: str, parent_id: int | None = None) -> int:
    payload = {"name": name}
    if parent_id:
        payload["parent_id"] = parent_id
    response = client.post("/api/v1/projects", json=payload)
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


def test_requirement_and_task_create_default_to_template_statuses_and_prd_fields(client: TestClient):
    project_id = _create_project(client)
    _, owner_id = _create_actor_token("Requirement Owner")

    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": "需求 CRUD", "priority": "3", "owner_id": owner_id},
    )
    assert requirement.status_code == 200
    assert requirement.json()["priority"] == "3"
    assert requirement.json()["status"] == "in_processing"

    default_priority_requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"默认优先级-{uuid4().hex[:8]}"},
    )
    assert default_priority_requirement.status_code == 200
    assert default_priority_requirement.json()["priority"] == "3"
    assert default_priority_requirement.json()["status"] == "pending_assignment"

    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "requirement_id": requirement.json()["id"], "title": "任务 CRUD", "owner_id": owner_id},
    )
    assert task.status_code == 200
    assert task.json()["requirement_id"] == requirement.json()["id"]
    assert task.json()["status"] == "in_processing"

    updated = client.patch(f"/api/v1/tasks/{task.json()['id']}", json={"actual_hours": 1.5})
    assert updated.status_code == 200
    assert updated.json()["actual_hours"] == 1.5


def test_generated_task_inherits_requirement_current_handler_by_default(client: TestClient):
    project_id = _create_project(client)
    _, owner_id = _create_actor_token("需求负责人")
    requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project_id,
            "title": "需求生成任务",
            "priority": "1",
            "owner_id": owner_id,
            "review_status": "not_required",
        },
    )
    assert requirement.status_code == 200

    generated = client.post(
        f"/api/v1/requirements/{requirement.json()['id']}/generate-task",
        json={"title": "实现需求生成任务", "task_type": "requirement_implementation"},
    )
    assert generated.status_code == 200
    data = generated.json()
    assert data["requirement_id"] == requirement.json()["id"]
    assert data["project_id"] == project_id
    assert data["owner_id"] == owner_id
    assert data["status"] == "in_processing"
    assert data["source_requirement_review_status"] == "not_required"


def test_requirement_update_records_only_changed_fields(client: TestClient):
    token, actor_id = _create_actor_token("Requirement Auditor")
    project_id = _create_project(client)
    requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project_id,
            "title": f"编辑记录需求-{uuid4().hex[:8]}",
            "priority": "3",
            "description": "原描述",
            "owner_id": actor_id,
        },
    ).json()

    updated = client.patch(
        f"/api/v1/requirements/{requirement['id']}",
        json={"title": "编辑后需求", "priority": "2", "description": "原描述"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert updated.status_code == 200

    logs = client.get(f"/api/v1/requirements/{requirement['id']}/audit-logs")
    assert logs.status_code == 200
    data = logs.json()
    assert len(data) == 1
    assert data[0]["action"] == "update"
    assert data[0]["actor_id"] == actor_id
    assert data[0]["before_data"] == {"title": requirement["title"], "priority": "3"}
    assert data[0]["after_data"] == {"title": "编辑后需求", "priority": "2"}


def test_task_update_records_only_changed_fields(client: TestClient):
    token, actor_id = _create_actor_token("Task Auditor")
    project_id = _create_project(client)
    task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "title": f"任务编辑记录-{uuid4().hex[:8]}",
            "description": "原描述",
            "priority": "medium",
            "owner_id": actor_id,
        },
    ).json()

    updated = client.patch(
        f"/api/v1/tasks/{task['id']}",
        json={"title": "任务编辑后标题", "description": "原描述", "priority": "high"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert updated.status_code == 200

    logs = client.get(f"/api/v1/tasks/{task['id']}/audit-logs")
    assert logs.status_code == 200
    data = logs.json()
    assert len(data) == 1
    assert data[0]["action"] == "update"
    assert data[0]["actor_id"] == actor_id
    assert data[0]["before_data"] == {"title": task["title"], "priority": "medium"}
    assert data[0]["after_data"] == {"title": "任务编辑后标题", "priority": "high"}


def test_requirement_cancel_records_history_through_runtime(client: TestClient):
    project_id = _create_project(client)
    token, owner_id = _create_actor_token("Requirement Closer")
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"Cancelable requirement {uuid4().hex[:8]}", "owner_id": owner_id},
    )
    assert requirement.status_code == 200

    canceled = _runtime_transition(
        client,
        "requirement",
        requirement.json()["id"],
        "cancel",
        token,
        {"reason": "done", "remark": "scope removed"},
    )

    assert canceled.status_code == 200
    assert canceled.json()["status"] == "canceled"
    history = client.get(f"/api/v1/requirements/{requirement.json()['id']}/status-operations")
    assert history.status_code == 200
    assert history.json()[-1]["action"] == "cancel"
    assert history.json()[-1]["reason"] == "done"
    assert history.json()[-1]["remark"] == "scope removed"

def test_requirement_close_blocks_on_open_linked_tasks_and_does_not_cancel_them(client: TestClient):
    project_id = _create_project(client)
    token, owner_id = _create_actor_token("Requirement Handler")
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"Blocked requirement {uuid4().hex[:8]}", "owner_id": owner_id},
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "requirement_id": requirement["id"], "title": f"Open task {uuid4().hex[:8]}", "owner_id": owner_id},
    ).json()

    blocked = _runtime_transition(
        client,
        "requirement",
        requirement["id"],
        "cancel",
        token,
        {"reason": "not needed", "remark": "cancel requirement"},
    )

    assert blocked.status_code == 400
    assert client.get(f"/api/v1/requirements/{requirement['id']}").json()["status"] == "in_processing"
    assert client.get(f"/api/v1/tasks/{task['id']}").json()["status"] == "in_processing"

def test_requirement_complete_goes_directly_to_completed_and_blocks_on_open_tasks(client: TestClient):
    project_id = _create_project(client)
    token, owner_id = _create_actor_token("Requirement Completer")
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"Completable requirement {uuid4().hex[:8]}", "owner_id": owner_id},
    ).json()

    completed = _runtime_transition(client, "requirement", requirement["id"], "complete", token)
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    history = client.get(f"/api/v1/requirements/{requirement['id']}/status-operations").json()
    assert history[-1]["action"] == "complete"

    blocked_requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"Blocked completion requirement {uuid4().hex[:8]}", "owner_id": owner_id},
    ).json()
    client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "requirement_id": blocked_requirement["id"], "title": f"Open task {uuid4().hex[:8]}", "owner_id": owner_id},
    )

    blocked = _runtime_transition(client, "requirement", blocked_requirement["id"], "complete", token)
    assert blocked.status_code == 400
    assert client.get(f"/api/v1/requirements/{blocked_requirement['id']}").json()["status"] == "in_processing"

def test_task_claim_and_cancel_follow_default_statuses(client: TestClient):
    project_id = _create_project(client)
    token, _ = _create_actor_token("Task Claimer")
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "title": f"Task status flow {uuid4().hex[:8]}"},
    )
    assert task.status_code == 200
    assert task.json()["status"] == "pending_assignment"

    claimed = _runtime_transition(client, "task", task.json()["id"], "claim", token)
    assert claimed.status_code == 200
    assert claimed.json()["status"] == "in_processing"

    canceled = _runtime_transition(
        client,
        "task",
        task.json()["id"],
        "cancel",
        token,
        {"reason": "not needed", "remark": "cancel task"},
    )
    assert canceled.status_code == 200
    assert canceled.json()["status"] == "canceled"

    history = client.get(f"/api/v1/tasks/{task.json()['id']}/status-operations")
    assert history.status_code == 200
    assert [item["action"] for item in history.json()][-2:] == ["claim", "cancel"]

def test_bug_fix_task_complete_routes_to_pending_confirmation(client: TestClient):
    project_id = _create_project(client)
    developer_token, developer_id = _create_actor_token("Task Developer", "developer")
    _, confirmer_id = _create_actor_token("Task Owner", "project_owner")
    _add_project_member(project_id, developer_id, "developer")
    _add_project_member(project_id, confirmer_id, "project_owner")
    task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "title": f"Bug fix task {uuid4().hex[:8]}",
            "task_type": "bug_fix",
            "owner_id": developer_id,
        },
    ).json()

    completed = _runtime_transition(client, "task", task["id"], "submit_confirmation", developer_token)

    assert completed.status_code == 200
    assert completed.json()["status"] == "pending_confirmation"
    assert completed.json()["owner_id"] == confirmer_id


def test_project_close_is_blocked_by_open_requirement_and_task(client: TestClient):
    project_id = _create_project(client)
    client.post(f"/api/v1/projects/{project_id}/start", json={"effective_time": "2026-06-01T09:00:00"})
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"项目关闭需求-{uuid4().hex[:8]}"},
    ).json()
    client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "requirement_id": requirement["id"], "title": f"项目关闭任务-{uuid4().hex[:8]}"},
    )

    closed_project = client.post(f"/api/v1/projects/{project_id}/close", json={"effective_time": "2026-06-10T18:00:00"})

    assert closed_project.status_code == 400
    assert client.get(f"/api/v1/projects/{project_id}").json()["status"] == "active"


def test_requirement_status_cannot_be_changed_by_form_save(client: TestClient):
    project_id = _create_project(client)
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"表单状态保护-{uuid4().hex[:8]}", "status": "active"},
    )
    assert requirement.status_code == 200
    assert requirement.json()["status"] == "pending_assignment"

    updated = client.patch(
        f"/api/v1/requirements/{requirement.json()['id']}",
        json={"title": "表单更新标题", "status": "closed"},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "表单更新标题"
    assert updated.json()["status"] == "pending_assignment"


def test_requirement_update_rejects_iteration_outside_project_scope(client: TestClient):
    operations_project = _create_named_project(client, "InnovateX operations")
    material_project = _create_named_project(client, "Material management", parent_id=operations_project)
    toxicology_project = _create_named_project(client, "Toxicology calculation")
    iteration_id = _create_iteration(client, operations_project, "InnovateX operations iteration 1.4.6")
    material_requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": material_project, "title": "Material requirement"},
    ).json()
    toxicology_requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": toxicology_project, "title": "Toxicology requirement"},
    ).json()

    accepted = client.patch(f"/api/v1/requirements/{material_requirement['id']}", json={"iteration_id": iteration_id})
    rejected = client.patch(f"/api/v1/requirements/{toxicology_requirement['id']}", json={"iteration_id": iteration_id})

    assert accepted.status_code == 200
    assert accepted.json()["iteration_id"] == iteration_id
    assert rejected.status_code == 400
    assert "scope" in rejected.json()["detail"].lower()


def test_deleting_requirement_unbinds_linked_test_cases(client: TestClient):
    project_id = _create_project(client)
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": f"Deleted requirement for case-{uuid4().hex[:8]}"},
    ).json()
    test_case = client.post(
        "/api/v1/test-cases",
        json={
            "project_id": project_id,
            "requirement_id": requirement["id"],
            "title": f"Case keeps visible after requirement delete-{uuid4().hex[:8]}",
        },
    ).json()

    deleted = client.delete(f"/api/v1/requirements/{requirement['id']}")

    assert deleted.status_code == 204
    db = SessionLocal()
    try:
        persisted_case = db.query(TestCase).filter(TestCase.id == test_case["id"]).first()
        assert persisted_case is not None
        assert persisted_case.requirement_id is None
    finally:
        db.close()
