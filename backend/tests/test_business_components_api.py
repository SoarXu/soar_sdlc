from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.session import SessionLocal
from app.models.project_member import ProjectMember
from app.models.user import User
from app.models.workflow_definition import WorkflowDefinition, WorkflowTransition
from app.models.business_component import WorkflowMigrationLog


def _create_project(client: TestClient, name: str, workflow_scheme_id: int | None = None) -> dict:
    payload = {"name": f"{name}-{uuid4().hex[:8]}"}
    if workflow_scheme_id is not None:
        payload["assignee_rule_config_id"] = workflow_scheme_id
    response = client.post("/api/v1/projects", json=payload)
    assert response.status_code == 200
    return response.json()


def _close_project(client: TestClient, project_id: int) -> None:
    started = client.post(
        f"/api/v1/projects/{project_id}/start",
        json={"effective_time": "2026-07-27T09:00:00"},
    )
    assert started.status_code == 200
    closed = client.post(
        f"/api/v1/projects/{project_id}/close",
        json={"effective_time": "2026-07-27T18:00:00"},
    )
    assert closed.status_code == 200


def _add_source_member(project_id: int, role: str = "developer") -> int:
    db = SessionLocal()
    try:
        user = User(
            username=f"component_member_{uuid4().hex[:8]}",
            full_name="Copied Component Member",
            password_hash=get_password_hash("User123456"),
            is_active=True,
        )
        db.add(user)
        db.flush()
        db.add(ProjectMember(project_id=project_id, user_id=user.id, project_role=role))
        db.commit()
        return user.id
    finally:
        db.close()


def _add_project_user_with_token(project_id: int, role: str = "developer") -> tuple[int, str]:
    db = SessionLocal()
    try:
        user = User(
            username=f"component_actor_{uuid4().hex[:8]}",
            full_name="Component Actor",
            password_hash=get_password_hash("User123456"),
            is_active=True,
        )
        db.add(user)
        db.flush()
        db.add(ProjectMember(project_id=project_id, user_id=user.id, project_role=role))
        db.commit()
        return user.id, create_access_token(user.username)
    finally:
        db.close()


def _create_enabled_workflow_scheme(client: TestClient) -> int:
    created = client.post(
        "/api/v1/assignee-rule-configs",
        json={
            "name": f"QA Source Workflow-{uuid4().hex[:8]}",
            "creation_mode": "template",
            "template_source": {"source_type": "system", "source_id": "system-standard"},
        },
    )
    assert created.status_code == 201, created.text
    enabled = client.post(f"/api/v1/assignee-rule-configs/{created.json()['id']}/enable")
    assert enabled.status_code == 200, enabled.text
    return created.json()["id"]


def test_create_business_component_from_closed_source_project(client: TestClient):
    operations_project = _create_project(client, "InnovateX Platform Operations")
    source_project = _create_project(client, "QA Archive Management")
    _close_project(client, source_project["id"])

    created = client.post(
        f"/api/v1/projects/{operations_project['id']}/business-components/from-project",
        json={"source_project_id": source_project["id"], "name": "QA Archive Management"},
    )

    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["project_id"] == operations_project["id"]
    assert payload["source_project_id"] == source_project["id"]
    assert payload["source_project_name_snapshot"] == source_project["name"]
    assert payload["name"] == "QA Archive Management"


def test_business_component_rejects_active_or_duplicate_source_project(client: TestClient):
    operations_project = _create_project(client, "InnovateX Platform Operations")
    active_source = _create_project(client, "Active QA Archive")

    active_response = client.post(
        f"/api/v1/projects/{operations_project['id']}/business-components/from-project",
        json={"source_project_id": active_source["id"], "name": "Active QA Archive"},
    )

    assert active_response.status_code == 409

    _close_project(client, active_source["id"])
    first = client.post(
        f"/api/v1/projects/{operations_project['id']}/business-components/from-project",
        json={"source_project_id": active_source["id"], "name": "QA Archive"},
    )
    duplicate = client.post(
        f"/api/v1/projects/{operations_project['id']}/business-components/from-project",
        json={"source_project_id": active_source["id"], "name": "QA Archive Duplicate"},
    )

    assert first.status_code == 201, first.text
    assert duplicate.status_code == 409


def test_component_creation_copies_source_members_into_independent_component_team(client: TestClient):
    operations_project = _create_project(client, "InnovateX Platform Operations")
    source_project = _create_project(client, "QA Archive Management")
    source_member_id = _add_source_member(source_project["id"], role="tester")
    _close_project(client, source_project["id"])

    created = client.post(
        f"/api/v1/projects/{operations_project['id']}/business-components/from-project",
        json={"source_project_id": source_project["id"], "name": "QA Archive Management"},
    )

    assert created.status_code == 201, created.text
    assert created.json()["members"] == [
        {"user_id": source_member_id, "component_role": "reviewer", "enabled": True}
    ]
    target_members = client.get(f"/api/v1/projects/{operations_project['id']}/members")
    assert source_member_id in {member["user_id"] for member in target_members.json()}


def test_component_creation_clones_source_project_workflow_scheme(client: TestClient):
    source_scheme_id = _create_enabled_workflow_scheme(client)
    operations_project = _create_project(client, "InnovateX Platform Operations")
    source_project = _create_project(client, "QA Archive Management", workflow_scheme_id=source_scheme_id)
    _close_project(client, source_project["id"])

    created = client.post(
        f"/api/v1/projects/{operations_project['id']}/business-components/from-project",
        json={"source_project_id": source_project["id"], "name": "QA Archive Management"},
    )

    assert created.status_code == 201, created.text
    assert created.json()["workflow_scheme_id"] is not None
    assert created.json()["workflow_scheme_id"] != source_scheme_id
    schemes = client.get("/api/v1/assignee-rule-configs").json()
    cloned = next(item for item in schemes if item["id"] == created.json()["workflow_scheme_id"])
    assert cloned["lifecycle_status"] == "enabled"


def test_component_members_are_maintained_independently_from_source_project(client: TestClient):
    operations_project = _create_project(client, "InnovateX Platform Operations")
    source_project = _create_project(client, "QA Archive Management")
    source_member_id = _add_source_member(source_project["id"], role="developer")
    target_member_id = _add_source_member(operations_project["id"], role="tester")
    _close_project(client, source_project["id"])
    component = client.post(
        f"/api/v1/projects/{operations_project['id']}/business-components/from-project",
        json={"source_project_id": source_project["id"], "name": "QA Archive Management"},
    ).json()

    replaced = client.put(
        f"/api/v1/projects/{operations_project['id']}/business-components/{component['id']}/members",
        json=[{"user_id": target_member_id, "component_role": "reviewer"}],
    )

    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["members"] == [
        {"user_id": target_member_id, "component_role": "reviewer", "enabled": True}
    ]
    source_members = client.get(f"/api/v1/projects/{source_project['id']}/members").json()
    assert source_member_id in {member["user_id"] for member in source_members}
    assert target_member_id not in {member["user_id"] for member in source_members}


def test_requirement_uses_primary_component_for_source_and_workflow(client: TestClient):
    source_scheme_id = _create_enabled_workflow_scheme(client)
    operations_project = _create_project(client, "InnovateX Platform Operations")
    source_project = _create_project(client, "QA Archive Management", workflow_scheme_id=source_scheme_id)
    _close_project(client, source_project["id"])
    component = client.post(
        f"/api/v1/projects/{operations_project['id']}/business-components/from-project",
        json={"source_project_id": source_project["id"], "name": "QA Archive Management"},
    ).json()

    requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": operations_project["id"],
            "title": "QA archive production issue",
            "primary_component_id": component["id"],
        },
    )

    assert requirement.status_code == 200, requirement.text
    payload = requirement.json()
    assert payload["project_id"] == operations_project["id"]
    assert payload["source_project_id"] == source_project["id"]
    assert payload["workflow_definition_id"] != source_project["workflow_definition_id"]
    assert payload["primary_component"]["id"] == component["id"]
    assert payload["related_components"] == []


def test_task_and_bug_inherit_primary_component_from_requirement(client: TestClient):
    operations_project = _create_project(client, "InnovateX Platform Operations")
    source_project = _create_project(client, "QA Archive Management")
    _close_project(client, source_project["id"])
    component = client.post(
        f"/api/v1/projects/{operations_project['id']}/business-components/from-project",
        json={"source_project_id": source_project["id"], "name": "QA Archive Management"},
    ).json()
    requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": operations_project["id"],
            "title": "QA archive production issue",
            "primary_component_id": component["id"],
        },
    ).json()

    task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": operations_project["id"],
            "requirement_id": requirement["id"],
            "title": "Investigate QA archive issue",
        },
    )
    bug = client.post(
        "/api/v1/bugs",
        json={
            "project_id": operations_project["id"],
            "requirement_id": requirement["id"],
            "title": "QA archive defect",
        },
    )

    assert task.status_code == 200, task.text
    assert task.json()["primary_component"]["id"] == component["id"]
    assert bug.status_code == 200, bug.text
    assert bug.json()["primary_component"]["id"] == component["id"]


def test_primary_component_membership_restricts_available_workflow_actions(client: TestClient):
    operations_project = _create_project(client, "InnovateX Platform Operations")
    source_project = _create_project(client, "QA Archive Management")
    source_member_id, source_token = _add_project_user_with_token(source_project["id"])
    _, outsider_token = _add_project_user_with_token(operations_project["id"])
    _close_project(client, source_project["id"])
    component = client.post(
        f"/api/v1/projects/{operations_project['id']}/business-components/from-project",
        json={"source_project_id": source_project["id"], "name": "QA Archive Management"},
    ).json()
    requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": operations_project["id"],
            "title": "QA archive production issue",
            "primary_component_id": component["id"],
        },
    ).json()

    member_actions = client.get(
        f"/api/v1/workflow-runtime/requirement/{requirement['id']}/transitions",
        headers={"Authorization": f"Bearer {source_token}"},
    )
    outsider_actions = client.get(
        f"/api/v1/workflow-runtime/requirement/{requirement['id']}/transitions",
        headers={"Authorization": f"Bearer {outsider_token}"},
    )

    assert member_actions.status_code == 200
    assert member_actions.json()
    assert outsider_actions.status_code == 200
    assert outsider_actions.json() == []
    assert source_member_id in {member["user_id"] for member in component["members"]}


def test_component_transition_route_limits_action_to_configured_member(client: TestClient):
    operations_project = _create_project(client, "InnovateX Platform Operations")
    source_project = _create_project(client, "QA Archive Management")
    source_member_id, source_token = _add_project_user_with_token(source_project["id"])
    _, outsider_token = _add_project_user_with_token(operations_project["id"])
    _close_project(client, source_project["id"])
    component = client.post(
        f"/api/v1/projects/{operations_project['id']}/business-components/from-project",
        json={"source_project_id": source_project["id"], "name": "QA Archive Management"},
    ).json()
    requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": operations_project["id"],
            "title": "QA archive production issue",
            "primary_component_id": component["id"],
        },
    ).json()
    actions = client.get(
        f"/api/v1/workflow-runtime/requirement/{requirement['id']}/transitions",
        headers={"Authorization": f"Bearer {source_token}"},
    ).json()
    assert actions

    saved = client.put(
        f"/api/v1/projects/{operations_project['id']}/business-components/{component['id']}/transition-routes",
        json=[
            {
                "object_type": "requirement",
                "transition_id": actions[0]["transition_id"],
                "eligible_member_mode": "users",
                "eligible_user_ids": str(source_member_id),
                "next_owner_mode": "user",
                "next_owner_user_id": source_member_id,
            }
        ],
    )
    assert saved.status_code == 200, saved.text
    assert client.get(
        f"/api/v1/workflow-runtime/requirement/{requirement['id']}/transitions",
        headers={"Authorization": f"Bearer {source_token}"},
    ).json()
    assert client.get(
        f"/api/v1/workflow-runtime/requirement/{requirement['id']}/transitions",
        headers={"Authorization": f"Bearer {outsider_token}"},
    ).json() == []


def test_workflow_migration_is_scoped_to_component_scheme_and_audited(client: TestClient):
    source_scheme_id = _create_enabled_workflow_scheme(client)
    operations_project = _create_project(client, "InnovateX Platform Operations")
    source_project = _create_project(client, "QA Archive Management", workflow_scheme_id=source_scheme_id)
    _close_project(client, source_project["id"])
    component = client.post(
        f"/api/v1/projects/{operations_project['id']}/business-components/from-project",
        json={"source_project_id": source_project["id"], "name": "QA Archive Management"},
    ).json()
    requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": operations_project["id"],
            "title": "QA archive production issue",
            "primary_component_id": component["id"],
        },
    ).json()
    db = SessionLocal()
    try:
        foreign_definition = (
            db.query(WorkflowDefinition)
            .filter(WorkflowDefinition.object_type == "requirement", WorkflowDefinition.id != requirement["workflow_definition_id"])
            .first()
        )
        assert foreign_definition
        foreign_transition = db.query(WorkflowTransition).filter(
            WorkflowTransition.definition_id == foreign_definition.id
        ).first()
        assert foreign_transition
        forbidden_state_id = foreign_transition.from_state_id
    finally:
        db.close()
    rejected = client.post(
        f"/api/v1/projects/{operations_project['id']}/business-components/{component['id']}/work-items/requirement/{requirement['id']}/workflow-migrations",
        json={"new_definition_id": foreign_definition.id, "new_state_id": forbidden_state_id, "reason": "must not cross schemes"},
    )
    assert rejected.status_code == 422, rejected.text

    migrated = client.post(
        f"/api/v1/projects/{operations_project['id']}/business-components/{component['id']}/work-items/requirement/{requirement['id']}/workflow-migrations",
        json={
            "new_definition_id": requirement["workflow_definition_id"],
            "new_state_id": requirement["current_state_id"],
            "reason": "confirm explicit migration audit",
        },
    )
    assert migrated.status_code == 200, migrated.text
    db = SessionLocal()
    try:
        assert db.query(WorkflowMigrationLog).filter(
            WorkflowMigrationLog.object_type == "requirement",
            WorkflowMigrationLog.object_id == requirement["id"],
        ).count() == 1
    finally:
        db.close()
