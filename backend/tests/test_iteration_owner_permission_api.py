from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.session import SessionLocal
from app.models.project_member import ProjectMember
from app.models.status_operation import StatusOperationLog
from app.models.user import User


def _create_user(full_name: str) -> tuple[int, str]:
    db = SessionLocal()
    try:
        user = User(
            username=f"iteration_owner_{uuid4().hex[:8]}",
            full_name=full_name,
            password_hash=get_password_hash("User123456"),
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id, create_access_token(user.username)
    finally:
        db.close()


def _add_project_member(project_id: int, user_id: int) -> None:
    db = SessionLocal()
    try:
        db.add(
            ProjectMember(
                project_id=project_id,
                user_id=user_id,
                project_role="developer",
                is_workbench_participant=True,
            )
        )
        db.commit()
    finally:
        db.close()


def test_iteration_owner_can_update_delivery_plan(client: TestClient):
    owner_id, owner_token = _create_user("Iteration Delivery Owner")
    project = client.post(
        "/api/v1/projects",
        json={"name": f"Iteration Owner Project {uuid4().hex[:8]}"},
    ).json()
    _add_project_member(project["id"], owner_id)
    iteration = client.post(
        "/api/v1/iterations",
        json={
            "project_ids": [project["id"]],
            "name": f"Iteration Owner Plan {uuid4().hex[:8]}",
            "owner_id": owner_id,
        },
    ).json()

    response = client.patch(
        f"/api/v1/iterations/{iteration['id']}",
        json={"name": "Updated delivery plan", "goal": "Ship the scoped release"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Updated delivery plan"
    assert response.json()["goal"] == "Ship the scoped release"


def test_iteration_owner_can_manage_scope_but_cannot_reassign_or_delete(client: TestClient):
    owner_id, owner_token = _create_user("Iteration Scope Owner")
    replacement_id, _ = _create_user("Iteration Replacement Owner")
    project = client.post(
        "/api/v1/projects",
        json={"name": f"Iteration Scope Project {uuid4().hex[:8]}"},
    ).json()
    _add_project_member(project["id"], owner_id)
    _add_project_member(project["id"], replacement_id)
    iteration = client.post(
        "/api/v1/iterations",
        json={
            "project_ids": [project["id"]],
            "name": f"Iteration Scope {uuid4().hex[:8]}",
            "owner_id": owner_id,
        },
    ).json()
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "title": f"Scoped requirement {uuid4().hex[:8]}"},
    ).json()

    linked = client.post(
        f"/api/v1/iterations/{iteration['id']}/requirements",
        json={"requirement_ids": [requirement["id"]]},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    reassigned = client.patch(
        f"/api/v1/iterations/{iteration['id']}",
        json={"owner_id": replacement_id},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    deleted = client.delete(
        f"/api/v1/iterations/{iteration['id']}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert linked.status_code == 200, linked.text
    assert reassigned.status_code == 403
    assert deleted.status_code == 403


def test_iteration_owner_can_execute_lifecycle_transition(client: TestClient):
    owner_id, owner_token = _create_user("Iteration Lifecycle Owner")
    project = client.post(
        "/api/v1/projects",
        json={"name": f"Iteration Lifecycle Project {uuid4().hex[:8]}"},
    ).json()
    _add_project_member(project["id"], owner_id)
    iteration = client.post(
        "/api/v1/iterations",
        json={
            "project_ids": [project["id"]],
            "name": f"Iteration Lifecycle {uuid4().hex[:8]}",
            "owner_id": owner_id,
        },
    ).json()

    transition = client.post(
        f"/api/v1/workflow-runtime/iteration/{iteration['id']}/transition",
        json={"action_key": "start"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert transition.status_code == 200, transition.text


def test_iteration_governance_override_requires_reason(client: TestClient):
    owner_id, _ = _create_user("Iteration Governed Owner")
    project = client.post(
        "/api/v1/projects",
        json={"name": f"Iteration Governed Project {uuid4().hex[:8]}"},
    ).json()
    _add_project_member(project["id"], owner_id)
    iteration = client.post(
        "/api/v1/iterations",
        json={
            "project_ids": [project["id"]],
            "name": f"Iteration Governed {uuid4().hex[:8]}",
            "owner_id": owner_id,
        },
    ).json()

    response = client.post(
        f"/api/v1/workflow-runtime/iteration/{iteration['id']}/transition",
        json={"action_key": "start"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Delegate reason is required"


def test_parent_project_owner_can_override_iteration_lifecycle_with_reason(client: TestClient):
    parent_owner_id, parent_owner_token = _create_user("Parent Iteration Governor")
    iteration_owner_id, _ = _create_user("Child Iteration Owner")
    parent = client.post(
        "/api/v1/projects",
        json={"name": f"Parent Iteration Project {uuid4().hex[:8]}", "owner_id": parent_owner_id},
    ).json()
    child = client.post(
        "/api/v1/projects",
        json={"name": f"Child Iteration Project {uuid4().hex[:8]}", "parent_id": parent["id"]},
    ).json()
    _add_project_member(child["id"], iteration_owner_id)
    iteration = client.post(
        "/api/v1/iterations",
        json={
            "project_ids": [child["id"]],
            "name": f"Parent Governed Iteration {uuid4().hex[:8]}",
            "owner_id": iteration_owner_id,
        },
    ).json()

    response = client.post(
        f"/api/v1/workflow-runtime/iteration/{iteration['id']}/transition",
        json={"action_key": "start", "delegate_reason": "Release governance intervention"},
        headers={"Authorization": f"Bearer {parent_owner_token}"},
    )

    assert response.status_code == 200, response.text
    db = SessionLocal()
    try:
        operation = (
            db.query(StatusOperationLog)
            .filter(
                StatusOperationLog.object_type == "iteration",
                StatusOperationLog.object_id == iteration["id"],
            )
            .order_by(StatusOperationLog.id.desc())
            .first()
        )
        assert operation is not None
        assert operation.delegate_reason == "Release governance intervention"
    finally:
        db.close()


def test_iteration_owner_loses_delivery_permission_after_membership_removal(client: TestClient):
    owner_id, owner_token = _create_user("Removed Iteration Owner")
    project = client.post(
        "/api/v1/projects",
        json={"name": f"Removed Owner Project {uuid4().hex[:8]}"},
    ).json()
    _add_project_member(project["id"], owner_id)
    iteration = client.post(
        "/api/v1/iterations",
        json={
            "project_ids": [project["id"]],
            "name": f"Removed Owner Iteration {uuid4().hex[:8]}",
            "owner_id": owner_id,
        },
    ).json()
    db = SessionLocal()
    try:
        db.query(ProjectMember).filter(
            ProjectMember.project_id == project["id"],
            ProjectMember.user_id == owner_id,
        ).delete()
        db.commit()
    finally:
        db.close()

    response = client.patch(
        f"/api/v1/iterations/{iteration['id']}",
        json={"goal": "This update must be rejected"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert response.status_code == 403
