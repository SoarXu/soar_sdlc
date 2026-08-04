from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import SessionLocal
from app.core.security import get_password_hash
from app.core.security import create_access_token
from app.models.user import User
from app.models.requirement import Requirement
from app.models.task import Task
from app.models.bug import Bug
from app.models.business_component import BusinessComponent
from app.models.program import Program
from app.models.project import Project
from app.models.assignee_rule_config import AssigneeRuleConfig
from app.models.workflow_definition import WorkflowDefinition, WorkflowState, WorkflowTransition


def _create_program_permission_user(full_name: str) -> tuple[int, str]:
    db = SessionLocal()
    try:
        user = User(
            username=f"program_permission_api_{uuid4().hex[:8]}",
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


def _program_auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _seed_program(
    *,
    owner_id: int | None,
    parent_id: int | None = None,
    status: str = "planning",
) -> Program:
    db = SessionLocal()
    try:
        program = Program(
            name=f"Program Permission API {uuid4().hex[:8]}",
            owner_id=owner_id,
            parent_id=parent_id,
            status=status,
        )
        db.add(program)
        db.commit()
        db.refresh(program)
        return program
    finally:
        db.close()


def _seed_program_project(*, program_id: int, state_category: str) -> Project:
    db = SessionLocal()
    try:
        state = db.query(WorkflowState).filter(WorkflowState.category == state_category).first()
        assert state is not None
        project = Project(
            name=f"Program Permission Project {uuid4().hex[:8]}",
            program_id=program_id,
            workflow_definition_id=state.definition_id,
            current_state_id=state.id,
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return project
    finally:
        db.close()


def _seed_business_component(project_id: int) -> BusinessComponent:
    db = SessionLocal()
    try:
        component = BusinessComponent(
            project_id=project_id,
            name=f"Program Permission Component {uuid4().hex[:8]}",
        )
        db.add(component)
        db.commit()
        db.refresh(component)
        return component
    finally:
        db.close()


def _first_current_transition_id(object_type: str, object_id: int) -> int:
    model_by_type = {
        "requirement": Requirement,
        "task": Task,
        "bug": Bug,
    }
    db = SessionLocal()
    try:
        item = db.query(model_by_type[object_type]).filter(model_by_type[object_type].id == object_id).one()
        transitions = (
            db.query(WorkflowTransition)
            .filter(
                WorkflowTransition.definition_id == item.workflow_definition_id,
                WorkflowTransition.from_state_id == item.current_state_id,
                WorkflowTransition.enabled.is_(True),
            )
            .order_by(WorkflowTransition.sort_order.asc(), WorkflowTransition.id.asc())
            .all()
        )
        transition = next(
            (
                candidate
                for candidate in transitions
                if not (candidate.ui_config or {}).get("hidden")
                and not (candidate.ui_config or {}).get("system_action")
                and not (candidate.ui_config or {}).get("command_type")
                and (candidate.ui_config or {}).get("action_category", "process") == "process"
            ),
            None,
        )
        assert transition is not None
        return transition.id
    finally:
        db.close()


def test_ancestor_program_owner_governs_descendant_project_but_not_its_work_items(client: TestClient):
    governor_id, governor_token = _create_program_permission_user("Project Governance Program Owner")
    handler_id, _handler_token = _create_program_permission_user("Project Work Item Handler")
    root = _seed_program(owner_id=governor_id)
    descendant = _seed_program(owner_id=None, parent_id=root.id)

    created = client.post(
        "/api/v1/projects",
        json={"name": f"Descendant Governed Project {uuid4().hex[:8]}", "program_id": descendant.id},
        headers=_program_auth(governor_token),
    )

    assert created.status_code == 200, created.text
    project = created.json()
    assert project["owner_id"] is None

    updated = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"description": "ancestor program governor can update metadata"},
        headers=_program_auth(governor_token),
    )
    members = client.put(
        f"/api/v1/projects/{project['id']}/members",
        json=[{"user_id": handler_id, "project_role": "developer", "sort_order": 0}],
        headers=_program_auth(governor_token),
    )
    started = client.post(
        f"/api/v1/projects/{project['id']}/start",
        json={"effective_time": "2026-07-30T09:00:00"},
        headers=_program_auth(governor_token),
    )
    status_history = client.get(
        f"/api/v1/projects/{project['id']}/status-operations",
        headers=_program_auth(governor_token),
    )
    audit_history = client.get(
        f"/api/v1/projects/{project['id']}/audit-logs",
        headers=_program_auth(governor_token),
    )

    assert updated.status_code == 200
    assert members.status_code == 200
    assert started.status_code == 200
    assert status_history.status_code == 200
    assert audit_history.status_code == 200

    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "title": "Protected requirement", "owner_id": handler_id},
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project["id"],
            "title": "Protected task",
            "task_type": "standalone_operation",
            "owner_id": handler_id,
        },
    ).json()
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project["id"], "title": "Protected bug", "owner_id": handler_id},
    ).json()

    assert {requirement["owner_id"], task["owner_id"], bug["owner_id"]} == {handler_id}
    for endpoint, work_item in (("requirements", requirement), ("tasks", task), ("bugs", bug)):
        rejected_create = client.post(
            f"/api/v1/{endpoint}",
            json={
                "project_id": project["id"],
                "title": f"Program governor cannot create {endpoint}",
                "owner_id": governor_id,
                **({"task_type": "standalone_operation"} if endpoint == "tasks" else {}),
            },
            headers=_program_auth(governor_token),
        )
        rejected_update = client.patch(
            f"/api/v1/{endpoint}/{work_item['id']}",
            json=(
                {"severity": "1"}
                if endpoint == "bugs"
                else {"description": "program governance is not work-item ownership"}
            ),
            headers=_program_auth(governor_token),
        )
        rejected_transition = client.post(
            f"/api/v1/workflow-runtime/{endpoint[:-1]}/{work_item['id']}/transition",
            json={"transition_id": _first_current_transition_id(endpoint[:-1], work_item["id"])},
            headers={**_program_auth(governor_token), "X-Test-Raw-Transition-Request": "1"},
        )
        rejected_delete = client.delete(
            f"/api/v1/{endpoint}/{work_item['id']}",
            headers=_program_auth(governor_token),
        )

        assert rejected_create.status_code == 403
        assert rejected_update.status_code == 403
        assert rejected_transition.status_code == 403
        assert rejected_delete.status_code == 403


def test_program_governor_cannot_change_business_workflows_or_iteration_work_item_associations(client: TestClient):
    governor_id, governor_token = _create_program_permission_user("Governance Boundary Program Owner")
    root = _seed_program(owner_id=governor_id)
    descendant = _seed_program(owner_id=None, parent_id=root.id)
    project = client.post(
        "/api/v1/projects",
        json={"name": f"Governance Boundary Project {uuid4().hex[:8]}", "program_id": descendant.id},
    ).json()
    component = _seed_business_component(project["id"])
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "title": "Governance boundary requirement"},
    ).json()
    transition_id = _first_current_transition_id("requirement", requirement["id"])
    source_iteration = client.post(
        "/api/v1/iterations",
        json={"name": f"Governance source iteration {uuid4().hex[:8]}", "project_ids": [project["id"]]},
    ).json()
    target_iteration = client.post(
        "/api/v1/iterations",
        json={"name": f"Governance target iteration {uuid4().hex[:8]}", "project_ids": [project["id"]]},
    ).json()

    route_update = client.put(
        f"/api/v1/projects/{project['id']}/business-components/{component.id}/transition-routes",
        json=[{"object_type": "requirement", "transition_id": transition_id}],
        headers=_program_auth(governor_token),
    )
    workflow_migration = client.post(
        f"/api/v1/projects/{project['id']}/business-components/{component.id}/work-items/requirement/{requirement['id']}/workflow-migrations",
        json={
            "new_definition_id": requirement["workflow_definition_id"],
            "new_state_id": requirement["current_state_id"],
            "reason": "program governance must not migrate workflow",
        },
        headers=_program_auth(governor_token),
    )
    link_requirement = client.post(
        f"/api/v1/iterations/{source_iteration['id']}/requirements",
        json={"requirement_ids": [requirement["id"]]},
        headers=_program_auth(governor_token),
    )
    defer_requirement = client.post(
        f"/api/v1/iterations/{source_iteration['id']}/defer-work-items",
        json={"target_iteration_id": target_iteration["id"], "requirement_ids": [requirement["id"]]},
        headers=_program_auth(governor_token),
    )

    assert route_update.status_code == 403
    assert workflow_migration.status_code == 403
    assert link_requirement.status_code == 403
    assert defer_requirement.status_code == 403


def test_program_governor_can_read_project_audit_but_not_work_item_comments_or_watches(client: TestClient):
    governor_id, governor_token = _create_program_permission_user("Project Audit Only Governor")
    root = _seed_program(owner_id=governor_id)
    descendant = _seed_program(owner_id=None, parent_id=root.id)
    project = client.post(
        "/api/v1/projects",
        json={"name": f"Project Audit Boundary {uuid4().hex[:8]}", "program_id": descendant.id},
        headers=_program_auth(governor_token),
    ).json()
    work_items = {
        "requirement": client.post(
            "/api/v1/requirements",
            json={"project_id": project["id"], "title": "Audit boundary requirement"},
        ).json(),
        "task": client.post(
            "/api/v1/tasks",
            json={
                "project_id": project["id"],
                "title": "Audit boundary task",
                "task_type": "standalone_operation",
            },
        ).json(),
        "bug": client.post(
            "/api/v1/bugs",
            json={"project_id": project["id"], "title": "Audit boundary bug"},
        ).json(),
    }

    assert client.get(
        f"/api/v1/projects/{project['id']}/status-operations",
        headers=_program_auth(governor_token),
    ).status_code == 200
    assert client.get(
        f"/api/v1/projects/{project['id']}/audit-logs",
        headers=_program_auth(governor_token),
    ).status_code == 200

    for object_type, work_item in work_items.items():
        comment_list = client.get(
            f"/api/v1/work-item-comments?object_type={object_type}&object_id={work_item['id']}",
            headers=_program_auth(governor_token),
        )
        comment_create = client.post(
            "/api/v1/work-item-comments",
            json={"object_type": object_type, "object_id": work_item["id"], "body": "unauthorized comment"},
            headers=_program_auth(governor_token),
        )
        watch_get = client.get(
            f"/api/v1/object-watches?object_type={object_type}&object_id={work_item['id']}",
            headers=_program_auth(governor_token),
        )
        watch_create = client.post(
            "/api/v1/object-watches",
            json={"object_type": object_type, "object_id": work_item["id"]},
            headers=_program_auth(governor_token),
        )
        watch_delete = client.delete(
            f"/api/v1/object-watches?object_type={object_type}&object_id={work_item['id']}",
            headers=_program_auth(governor_token),
        )

        assert comment_list.status_code == 403
        assert comment_create.status_code == 403
        assert watch_get.status_code == 403
        assert watch_create.status_code == 403
        assert watch_delete.status_code == 403

    added_membership = client.put(
        f"/api/v1/projects/{project['id']}/members",
        json=[{"user_id": governor_id, "project_role": "developer", "sort_order": 0}],
        headers=_program_auth(governor_token),
    )
    member_comment = client.post(
        "/api/v1/work-item-comments",
        json={
            "object_type": "requirement",
            "object_id": work_items["requirement"]["id"],
            "body": "project member comment",
        },
        headers=_program_auth(governor_token),
    )
    member_watch = client.post(
        "/api/v1/object-watches",
        json={"object_type": "requirement", "object_id": work_items["requirement"]["id"]},
        headers=_program_auth(governor_token),
    )

    assert added_membership.status_code == 200
    assert member_comment.status_code == 201
    assert member_watch.status_code == 200


def test_program_governor_creates_child_project_with_parent_program_inheritance(client: TestClient):
    governor_id, governor_token = _create_program_permission_user("Child Project Program Governor")
    program = _seed_program(owner_id=governor_id)
    parent = client.post(
        "/api/v1/projects",
        json={"name": f"Governed Parent Project {uuid4().hex[:8]}", "program_id": program.id},
    ).json()

    created = client.post(
        "/api/v1/projects",
        json={"name": f"Inherited Program Child Project {uuid4().hex[:8]}", "parent_id": parent["id"]},
        headers=_program_auth(governor_token),
    )

    assert created.status_code == 200, created.text
    assert created.json()["parent_id"] == parent["id"]
    assert created.json()["program_id"] == program.id


def test_program_governor_cannot_attach_project_to_parent_in_another_program(client: TestClient):
    governor_id, governor_token = _create_program_permission_user("Cross Program Parent Governor")
    governed_program = _seed_program(owner_id=governor_id)
    unrelated_program = _seed_program(owner_id=None)
    foreign_parent = client.post(
        "/api/v1/projects",
        json={"name": f"Foreign Parent Project {uuid4().hex[:8]}", "program_id": unrelated_program.id},
    ).json()
    project_name = f"Cross Program Project {uuid4().hex[:8]}"

    rejected = client.post(
        "/api/v1/projects",
        json={"name": project_name, "program_id": governed_program.id, "parent_id": foreign_parent["id"]},
        headers=_program_auth(governor_token),
    )

    assert rejected.status_code in {403, 422}
    assert not any(project["name"] == project_name for project in client.get("/api/v1/projects").json())


def test_parent_project_rejects_explicit_mismatched_program_id_even_for_governor_of_both(client: TestClient):
    governor_id, governor_token = _create_program_permission_user("Mismatched Program Governor")
    parent_program = _seed_program(owner_id=governor_id)
    mismatched_program = _seed_program(owner_id=governor_id)
    parent = client.post(
        "/api/v1/projects",
        json={"name": f"Mismatched Program Parent {uuid4().hex[:8]}", "program_id": parent_program.id},
    ).json()
    project_name = f"Mismatched Program Child {uuid4().hex[:8]}"

    rejected = client.post(
        "/api/v1/projects",
        json={"name": project_name, "parent_id": parent["id"], "program_id": mismatched_program.id},
        headers=_program_auth(governor_token),
    )

    assert rejected.status_code == 422
    assert not any(project["name"] == project_name for project in client.get("/api/v1/projects").json())


def test_program_governor_cannot_move_project_to_ungoverned_program_or_parent(client: TestClient):
    governor_id, governor_token = _create_program_permission_user("Source Only Program Governor")
    source_program = _seed_program(owner_id=governor_id)
    target_program = _seed_program(owner_id=None)
    program_move_project = client.post(
        "/api/v1/projects",
        json={"name": f"Program Move Source Project {uuid4().hex[:8]}", "program_id": source_program.id},
    ).json()
    parent_move_project = client.post(
        "/api/v1/projects",
        json={"name": f"Parent Move Source Project {uuid4().hex[:8]}", "program_id": source_program.id},
    ).json()
    target_parent = client.post(
        "/api/v1/projects",
        json={"name": f"Target Program Parent {uuid4().hex[:8]}", "program_id": target_program.id},
    ).json()

    program_move = client.patch(
        f"/api/v1/projects/{program_move_project['id']}",
        json={"program_id": target_program.id},
        headers=_program_auth(governor_token),
    )
    parent_move = client.patch(
        f"/api/v1/projects/{parent_move_project['id']}",
        json={"parent_id": target_parent["id"]},
        headers=_program_auth(governor_token),
    )

    assert program_move.status_code == 403
    assert parent_move.status_code == 403
    unchanged_program_move = client.get(f"/api/v1/projects/{program_move_project['id']}").json()
    unchanged_parent_move = client.get(f"/api/v1/projects/{parent_move_project['id']}").json()
    assert unchanged_program_move["program_id"] == source_program.id
    assert unchanged_parent_move["parent_id"] is None


def test_project_move_rejects_parent_program_mismatch_even_when_governing_all_targets(client: TestClient):
    governor_id, governor_token = _create_program_permission_user("All Targets Program Governor")
    source_program = _seed_program(owner_id=governor_id)
    parent_program = _seed_program(owner_id=governor_id)
    mismatched_program = _seed_program(owner_id=governor_id)
    source_project = client.post(
        "/api/v1/projects",
        json={"name": f"Mismatch Source Project {uuid4().hex[:8]}", "program_id": source_program.id},
    ).json()
    parent = client.post(
        "/api/v1/projects",
        json={"name": f"Mismatch Parent Project {uuid4().hex[:8]}", "program_id": parent_program.id},
    ).json()

    rejected = client.patch(
        f"/api/v1/projects/{source_project['id']}",
        json={"parent_id": parent["id"], "program_id": mismatched_program.id},
        headers=_program_auth(governor_token),
    )

    assert rejected.status_code == 422
    unchanged = client.get(f"/api/v1/projects/{source_project['id']}").json()
    assert unchanged["program_id"] == source_program.id
    assert unchanged["parent_id"] is None


def test_program_governor_can_move_project_when_governing_source_target_and_parent(client: TestClient):
    governor_id, governor_token = _create_program_permission_user("Cross Program Governor")
    source_program = _seed_program(owner_id=governor_id)
    target_program = _seed_program(owner_id=governor_id)
    source_project = client.post(
        "/api/v1/projects",
        json={"name": f"Movable Source Project {uuid4().hex[:8]}", "program_id": source_program.id},
    ).json()
    target_parent = client.post(
        "/api/v1/projects",
        json={"name": f"Movable Target Parent {uuid4().hex[:8]}", "program_id": target_program.id},
    ).json()

    moved = client.patch(
        f"/api/v1/projects/{source_project['id']}",
        json={"parent_id": target_parent["id"], "program_id": target_program.id},
        headers=_program_auth(governor_token),
    )

    assert moved.status_code == 200, moved.text
    assert moved.json()["program_id"] == target_program.id
    assert moved.json()["parent_id"] == target_parent["id"]


def test_project_creation_authenticates_before_validating_parent_project(client: TestClient):
    response = client.post(
        "/api/v1/projects",
        json={"name": f"Unauthenticated Parent Project {uuid4().hex[:8]}", "parent_id": 999999999},
        headers={"X-Test-No-Auth": "1"},
    )

    assert response.status_code == 401


def test_unrelated_user_cannot_create_or_govern_descendant_program_project(client: TestClient):
    governor_id, _governor_token = _create_program_permission_user("Related Program Governor")
    unrelated_id, unrelated_token = _create_program_permission_user("Unrelated Project User")
    root = _seed_program(owner_id=governor_id)
    descendant = _seed_program(owner_id=None, parent_id=root.id)
    project = client.post(
        "/api/v1/projects",
        json={"name": f"Unrelated Governance Project {uuid4().hex[:8]}", "program_id": descendant.id},
    ).json()

    rejected_creation = client.post(
        "/api/v1/projects",
        json={"name": f"Unauthorized Descendant Project {uuid4().hex[:8]}", "program_id": descendant.id},
        headers=_program_auth(unrelated_token),
    )
    rejected_update = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"description": "unrelated user cannot update"},
        headers=_program_auth(unrelated_token),
    )
    rejected_members = client.put(
        f"/api/v1/projects/{project['id']}/members",
        json=[{"user_id": unrelated_id, "project_role": "developer", "sort_order": 0}],
        headers=_program_auth(unrelated_token),
    )
    rejected_lifecycle = client.post(
        f"/api/v1/projects/{project['id']}/start",
        json={"effective_time": "2026-07-30T09:00:00"},
        headers=_program_auth(unrelated_token),
    )
    rejected_status_history = client.get(
        f"/api/v1/projects/{project['id']}/status-operations",
        headers=_program_auth(unrelated_token),
    )
    rejected_audit_history = client.get(
        f"/api/v1/projects/{project['id']}/audit-logs",
        headers=_program_auth(unrelated_token),
    )

    assert rejected_creation.status_code == 403
    assert rejected_update.status_code == 403
    assert rejected_members.status_code == 403
    assert rejected_lifecycle.status_code == 403
    assert rejected_status_history.status_code == 403
    assert rejected_audit_history.status_code == 403


def test_authenticated_user_creates_unbound_project_as_default_owner(client: TestClient):
    user_id, user_token = _create_program_permission_user("Unbound Project User")

    created_by_user = client.post(
        "/api/v1/projects",
        json={"name": f"User Unbound Project {uuid4().hex[:8]}"},
        headers=_program_auth(user_token),
    )
    created = client.post("/api/v1/projects", json={"name": f"Admin Unbound Project {uuid4().hex[:8]}"})

    assert user_id
    assert created_by_user.status_code == 200
    assert created_by_user.json()["owner_id"] == user_id
    assert created.status_code == 200


def test_any_authenticated_active_user_creates_root_program_and_becomes_default_owner(client: TestClient):
    actor_id, actor_token = _create_program_permission_user("Program Root Creator")

    created = client.post(
        "/api/v1/programs",
        json={"name": f"User Root Program {uuid4().hex[:8]}"},
        headers=_program_auth(actor_token),
    )

    assert created.status_code == 200, created.text
    assert created.json()["parent_id"] is None
    assert created.json()["owner_id"] == actor_id


def test_program_creation_requires_authentication(client: TestClient):
    response = client.post(
        "/api/v1/programs",
        json={"name": f"Unauthenticated Program {uuid4().hex[:8]}"},
        headers={"X-Test-No-Auth": "1"},
    )

    assert response.status_code == 401


def test_ancestor_program_owner_can_create_child_program(client: TestClient):
    owner_id, owner_token = _create_program_permission_user("Program Ancestor Owner")
    child_owner_id, _child_owner_token = _create_program_permission_user("Program Child Owner")
    root = _seed_program(owner_id=owner_id)

    created = client.post(
        "/api/v1/programs",
        json={
            "name": f"Owned Child Program {uuid4().hex[:8]}",
            "parent_id": root.id,
            "owner_id": child_owner_id,
        },
        headers=_program_auth(owner_token),
    )

    assert created.status_code == 200, created.text
    child = created.json()
    assert child["parent_id"] == root.id
    assert child["owner_id"] == child_owner_id

    grandchild = client.post(
        "/api/v1/programs",
        json={"name": f"Owned Grandchild Program {uuid4().hex[:8]}", "parent_id": child["id"]},
        headers=_program_auth(owner_token),
    )

    assert grandchild.status_code == 200, grandchild.text
    assert grandchild.json()["parent_id"] == child["id"]
    assert grandchild.json()["owner_id"] == owner_id


def test_unrelated_user_cannot_create_or_govern_child_program(client: TestClient):
    owner_id, _owner_token = _create_program_permission_user("Program Tree Owner")
    unrelated_id, unrelated_token = _create_program_permission_user("Unrelated Program User")
    replacement_owner_id, _replacement_owner_token = _create_program_permission_user("Replacement Program Owner")
    root = _seed_program(owner_id=owner_id)
    child = _seed_program(owner_id=None, parent_id=root.id)

    child_creation = client.post(
        "/api/v1/programs",
        json={"name": f"Unauthorized Child {uuid4().hex[:8]}", "parent_id": root.id},
        headers=_program_auth(unrelated_token),
    )
    update = client.patch(
        f"/api/v1/programs/{child.id}",
        json={"description": "unrelated user cannot update"},
        headers=_program_auth(unrelated_token),
    )
    lifecycle = client.post(
        f"/api/v1/programs/{child.id}/start",
        json={"effective_time": "2026-06-01T09:00:00"},
        headers=_program_auth(unrelated_token),
    )
    owner_transfer = client.patch(
        f"/api/v1/programs/{child.id}",
        json={"owner_id": replacement_owner_id},
        headers=_program_auth(unrelated_token),
    )

    assert unrelated_id != owner_id
    assert child_creation.status_code == 403
    assert update.status_code == 403
    assert lifecycle.status_code == 403
    assert owner_transfer.status_code == 403


def test_program_parent_change_requires_new_parent_governance_and_rejects_descendant_cycle(client: TestClient):
    owner_id, owner_token = _create_program_permission_user("Program Parent Owner")
    other_owner_id, _other_owner_token = _create_program_permission_user("Other Program Parent Owner")
    root = _seed_program(owner_id=owner_id)
    child = _seed_program(owner_id=None, parent_id=root.id)
    other_root = _seed_program(owner_id=other_owner_id)

    unauthorized_move = client.patch(
        f"/api/v1/programs/{child.id}",
        json={"parent_id": other_root.id},
        headers=_program_auth(owner_token),
    )
    cycle = client.patch(
        f"/api/v1/programs/{root.id}",
        json={"parent_id": child.id},
        headers=_program_auth(owner_token),
    )

    assert unauthorized_move.status_code == 403
    assert cycle.status_code == 422


def test_program_creation_rejects_inactive_or_deleted_explicit_owner(client: TestClient):
    creator_id, creator_token = _create_program_permission_user("Program Owner Validator")
    inactive_owner_id, _inactive_token = _create_program_permission_user("Inactive Program Owner")
    deleted_owner_id, _deleted_token = _create_program_permission_user("Deleted Program Owner")

    db = SessionLocal()
    try:
        db.query(User).filter(User.id == inactive_owner_id).update({"is_active": False})
        db.query(User).filter(User.id == deleted_owner_id).update({"deleted": 1})
        db.commit()
    finally:
        db.close()

    inactive = client.post(
        "/api/v1/programs",
        json={"name": f"Inactive Owner Program {uuid4().hex[:8]}", "owner_id": inactive_owner_id},
        headers=_program_auth(creator_token),
    )
    deleted = client.post(
        "/api/v1/programs",
        json={"name": f"Deleted Owner Program {uuid4().hex[:8]}", "owner_id": deleted_owner_id},
        headers=_program_auth(creator_token),
    )

    assert creator_id not in {inactive_owner_id, deleted_owner_id}
    assert inactive.status_code == 422
    assert deleted.status_code == 422


def test_program_owner_transfer_immediately_revokes_former_owner_governance(client: TestClient):
    former_owner_id, former_owner_token = _create_program_permission_user("Former Program Owner")
    replacement_owner_id, replacement_owner_token = _create_program_permission_user("Replacement Program Owner")
    program = _seed_program(owner_id=former_owner_id)

    transferred = client.patch(
        f"/api/v1/programs/{program.id}",
        json={"owner_id": replacement_owner_id},
        headers=_program_auth(former_owner_token),
    )
    former_owner_update = client.patch(
        f"/api/v1/programs/{program.id}",
        json={"description": "former owner cannot govern"},
        headers=_program_auth(former_owner_token),
    )
    former_owner_start = client.post(
        f"/api/v1/programs/{program.id}/start",
        json={"effective_time": "2026-06-01T09:00:00"},
        headers=_program_auth(former_owner_token),
    )
    replacement_update = client.patch(
        f"/api/v1/programs/{program.id}",
        json={"description": "replacement owner can govern"},
        headers=_program_auth(replacement_owner_token),
    )

    assert transferred.status_code == 200
    assert transferred.json()["owner_id"] == replacement_owner_id
    assert former_owner_update.status_code == 403
    assert former_owner_start.status_code == 403
    assert replacement_update.status_code == 200


def test_program_owner_transfer_rejects_inactive_or_deleted_replacement(client: TestClient):
    owner_id, owner_token = _create_program_permission_user("Program Owner Transfer Validator")
    inactive_owner_id, _inactive_token = _create_program_permission_user("Inactive Transfer Owner")
    deleted_owner_id, _deleted_token = _create_program_permission_user("Deleted Transfer Owner")
    program = _seed_program(owner_id=owner_id)

    db = SessionLocal()
    try:
        db.query(User).filter(User.id == inactive_owner_id).update({"is_active": False})
        db.query(User).filter(User.id == deleted_owner_id).update({"deleted": 1})
        db.commit()
    finally:
        db.close()

    inactive = client.patch(
        f"/api/v1/programs/{program.id}",
        json={"owner_id": inactive_owner_id},
        headers=_program_auth(owner_token),
    )
    deleted = client.patch(
        f"/api/v1/programs/{program.id}",
        json={"owner_id": deleted_owner_id},
        headers=_program_auth(owner_token),
    )

    assert inactive.status_code == 422
    assert deleted.status_code == 422


def test_program_audit_actors_are_authenticated_user_not_client_payload(client: TestClient):
    actor_id, actor_token = _create_program_permission_user("Program Audit Actor")
    forged_actor_id, _forged_actor_token = _create_program_permission_user("Forged Program Audit Actor")

    created = client.post(
        "/api/v1/programs",
        json={
            "name": f"Program Audit Actor {uuid4().hex[:8]}",
            "creator_id": forged_actor_id,
            "updater_id": forged_actor_id,
        },
        headers=_program_auth(actor_token),
    )
    assert created.status_code == 200
    assert created.json()["creator_id"] == actor_id
    assert created.json()["updater_id"] == actor_id

    updated = client.patch(
        f"/api/v1/programs/{created.json()['id']}",
        json={
            "description": "audit actor must be server controlled",
            "creator_id": forged_actor_id,
            "updater_id": forged_actor_id,
        },
        headers=_program_auth(actor_token),
    )

    assert updated.status_code == 200
    assert updated.json()["creator_id"] == actor_id
    assert updated.json()["updater_id"] == actor_id


def test_program_parent_change_requires_governance_on_old_and_new_parent(client: TestClient):
    old_parent_owner_id, old_parent_owner_token = _create_program_permission_user("Old Parent Program Owner")
    child_owner_id, child_owner_token = _create_program_permission_user("Child Only Program Owner")
    old_parent = _seed_program(owner_id=old_parent_owner_id)
    child_for_detach = _seed_program(owner_id=child_owner_id, parent_id=old_parent.id)
    child_for_move = _seed_program(owner_id=child_owner_id, parent_id=old_parent.id)
    child_for_approved_move = _seed_program(owner_id=child_owner_id, parent_id=old_parent.id)
    child_owner_root = _seed_program(owner_id=child_owner_id)
    old_parent_owner_root = _seed_program(owner_id=old_parent_owner_id)

    detached = client.patch(
        f"/api/v1/programs/{child_for_detach.id}",
        json={"parent_id": None},
        headers=_program_auth(child_owner_token),
    )
    moved_without_old_parent = client.patch(
        f"/api/v1/programs/{child_for_move.id}",
        json={"parent_id": child_owner_root.id},
        headers=_program_auth(child_owner_token),
    )
    approved_move = client.patch(
        f"/api/v1/programs/{child_for_approved_move.id}",
        json={"parent_id": old_parent_owner_root.id},
        headers=_program_auth(old_parent_owner_token),
    )

    assert detached.status_code == 403
    assert moved_without_old_parent.status_code == 403
    assert approved_move.status_code == 200
    assert approved_move.json()["parent_id"] == old_parent_owner_root.id


def test_program_owner_can_delete_nonempty_program_tree(client: TestClient):
    owner_id, owner_token = _create_program_permission_user("Program Delete Owner")
    empty_program = _seed_program(owner_id=owner_id)
    nonempty_program = _seed_program(owner_id=owner_id)
    _seed_program(owner_id=None, parent_id=nonempty_program.id)

    empty_deleted = client.delete(
        f"/api/v1/programs/{empty_program.id}",
        headers=_program_auth(owner_token),
    )
    nonempty_deleted = client.delete(
        f"/api/v1/programs/{nonempty_program.id}",
        headers=_program_auth(owner_token),
    )

    assert empty_deleted.status_code == 204
    assert nonempty_deleted.status_code == 204


def test_system_admin_deletes_nonempty_program_tree_only_when_closed_and_terminal(client: TestClient):
    root = _seed_program(owner_id=None, status="closed")
    child = _seed_program(owner_id=None, parent_id=root.id, status="planning")
    project = _seed_program_project(program_id=child.id, state_category="start")

    open_child = client.delete(f"/api/v1/programs/{root.id}")
    assert open_child.status_code == 403

    db = SessionLocal()
    try:
        terminal_state = db.query(WorkflowState).filter(WorkflowState.category == "terminal").first()
        assert terminal_state is not None
        terminal_state_id = terminal_state.id
        db.query(Program).filter(Program.id == child.id).update({"status": "closed"})
        db.commit()
    finally:
        db.close()

    open_project = client.delete(f"/api/v1/programs/{root.id}")
    assert open_project.status_code == 403

    db = SessionLocal()
    try:
        db.query(Project).filter(Project.id == project.id).update({"current_state_id": terminal_state_id})
        db.commit()
    finally:
        db.close()

    deleted = client.delete(f"/api/v1/programs/{root.id}")
    assert deleted.status_code == 204


def test_project_creation_binds_default_workflow_scheme(client: TestClient):
    created = client.post("/api/v1/projects", json={"name": f"ID 项目-{uuid4().hex[:8]}"})

    assert created.status_code == 200
    data = created.json()
    assert data["assignee_rule_config_id"] is not None
    assert isinstance(data["workflow_definition_id"], int)
    assert isinstance(data["current_state_id"], int)
    assert data["status_name"]

    db = SessionLocal()
    try:
        default_scheme = db.query(AssigneeRuleConfig).filter(
            AssigneeRuleConfig.name == "默认工作流规则"
        ).one()
        assert data["assignee_rule_config_id"] == default_scheme.id
        scheme_definition = db.query(WorkflowDefinition).filter(
            WorkflowDefinition.scope_type == "assignee_rule_config",
            WorkflowDefinition.scope_id == default_scheme.id,
            WorkflowDefinition.object_type == "project",
            WorkflowDefinition.enabled.is_(True),
        ).one()
        assert data["workflow_definition_id"] == scheme_definition.id
        state = db.query(WorkflowState).filter(WorkflowState.id == data["current_state_id"]).one()
        assert state.definition_id == data["workflow_definition_id"]
        assert data["status_name"] == state.status_name
        assert state.id == db.query(WorkflowState.id).filter(
            WorkflowState.id == data["current_state_id"],
            WorkflowState.category == "start",
        ).scalar()
    finally:
        db.close()


def test_project_runtime_uses_current_state_id_without_legacy_status_column(client: TestClient):
    project = client.post("/api/v1/projects", json={"name": f"ID runtime-{uuid4().hex[:8]}"}).json()
    initial_state_id = project["current_state_id"]

    db = SessionLocal()
    try:
        stored = db.execute(text("select id from projects where id = :id"), {"id": project["id"]}).one()
        assert stored.id == project["id"]
        columns = {row.Field for row in db.execute(text("SHOW COLUMNS FROM projects")).all()}
        assert "status" not in columns
    finally:
        db.close()

    actions = client.get(f"/api/v1/workflow-runtime/project/{project['id']}/transitions")
    assert actions.status_code == 200
    assert "start" in {item["action_key"] for item in actions.json()}

    started = client.post(
        f"/api/v1/workflow-runtime/project/{project['id']}/transition",
        json={"action_key": "start", "payload": {"effective_time": "2026-07-20"}},
    )
    assert started.status_code == 200, started.text
    assert started.json()["current_state_id"] != initial_state_id
    assert started.json()["workflow_definition_id"] == project["workflow_definition_id"]


def _configure_and_enable_scheme(client: TestClient, config_id: int) -> None:
    definitions = client.get(
        f"/api/v1/workflow-definitions?scope_type=assignee_rule_config&scope_id={config_id}"
    ).json()
    by_object_type = {item["object_type"]: item for item in definitions}
    for object_type in ("requirement", "task", "bug", "project"):
        assert client.post(
            f"/api/v1/workflow-definitions/{by_object_type[object_type]['id']}/apply-template"
        ).status_code == 200
    enabled = client.post(f"/api/v1/assignee-rule-configs/{config_id}/enable")
    assert enabled.status_code == 200, enabled.text


def test_project_creation_uses_selected_scheme_project_workflow(client: TestClient):
    config_response = client.post(
        "/api/v1/assignee-rule-configs",
        json={"name": f"Project Workflow Scheme-{uuid4().hex[:8]}"},
    )
    assert config_response.status_code == 201, config_response.text
    config = config_response.json()
    _configure_and_enable_scheme(client, config["id"])

    scheme_definitions = client.get(
        f"/api/v1/workflow-definitions?scope_type=assignee_rule_config&scope_id={config['id']}"
    ).json()
    scheme_project_definition = next(item for item in scheme_definitions if item["object_type"] == "project")

    scheme_project = client.post(
        "/api/v1/projects",
        json={
            "name": f"Scheme Project-{uuid4().hex[:8]}",
            "assignee_rule_config_id": config["id"],
        },
    )
    assert scheme_project.status_code == 200, scheme_project.text
    assert scheme_project.json()["workflow_definition_id"] == scheme_project_definition["id"]
    assert scheme_project.json()["current_state_id"] == scheme_project_definition["initial_state_id"]
    runtime_transitions = client.get(
        f"/api/v1/workflow-runtime/project/{scheme_project.json()['id']}/transitions"
    )
    assert runtime_transitions.status_code == 200, runtime_transitions.text
    runtime_transition_ids = [item["transition_id"] for item in runtime_transitions.json()]
    db = SessionLocal()
    try:
        runtime_definition_ids = {
            item.definition_id
            for item in db.query(WorkflowTransition)
            .filter(WorkflowTransition.id.in_(runtime_transition_ids))
            .all()
        }
    finally:
        db.close()
    assert runtime_definition_ids == {scheme_project_definition["id"]}

    default_project = client.post(
        "/api/v1/projects",
        json={"name": f"Default Scheme Project-{uuid4().hex[:8]}"},
    )
    assert default_project.status_code == 200, default_project.text
    db = SessionLocal()
    try:
        default_scheme = db.query(AssigneeRuleConfig).filter(
            AssigneeRuleConfig.name == "默认工作流规则"
        ).one()
        default_definition = db.query(WorkflowDefinition).filter(
            WorkflowDefinition.scope_type == "assignee_rule_config",
            WorkflowDefinition.scope_id == default_scheme.id,
            WorkflowDefinition.object_type == "project",
            WorkflowDefinition.enabled.is_(True),
        ).one()
    finally:
        db.close()
    assert default_project.json()["assignee_rule_config_id"] == default_scheme.id
    assert default_project.json()["workflow_definition_id"] == default_definition.id
    assert default_project.json()["current_state_id"] == default_definition.initial_state_id


def test_program_crud_persists_to_database(client: TestClient):
    name = f"项目集-{uuid4().hex[:8]}"

    created = client.post(
        "/api/v1/programs",
        json={
            "name": name,
            "planned_start_date": "2026-06-10",
            "planned_end_date": "2026-12-31",
            "actual_start_date": "2026-06-11",
            "actual_end_date": "2026-12-30",
            "description": "API 创建",
        },
    )
    assert created.status_code == 200
    created_data = created.json()
    program_id = created_data["id"]
    assert created_data["planned_start_date"] == "2026-06-10"
    assert created_data["planned_end_date"] == "2026-12-31"
    assert created_data["actual_start_date"] == "2026-06-11"
    assert created_data["actual_end_date"] == "2026-12-30"
    assert created_data["is_long_term"] is False
    assert created_data["status"] == "planning"

    db = SessionLocal()
    try:
        stored = db.execute(
            text("select name, planned_start_date, planned_end_date, actual_start_date, actual_end_date, is_long_term from programs where id = :id"),
            {"id": program_id},
        ).one()
        assert stored.name == name
        assert str(stored.planned_start_date) == "2026-06-10"
        assert str(stored.planned_end_date) == "2026-12-31"
        assert str(stored.actual_start_date) == "2026-06-11"
        assert str(stored.actual_end_date) == "2026-12-30"
        assert stored.is_long_term == 0
    finally:
        db.close()

    updated = client.patch(f"/api/v1/programs/{program_id}", json={"is_long_term": True, "actual_end_date": "2027-01-10"})
    assert updated.status_code == 200
    assert updated.json()["status"] == "planning"
    assert updated.json()["is_long_term"] is True
    assert updated.json()["planned_end_date"] is None
    assert updated.json()["actual_end_date"] == "2027-01-10"

    started = client.post(
        f"/api/v1/programs/{program_id}/start",
        json={"effective_time": "2026-06-10T09:00:00"},
    )
    assert started.status_code == 200
    assert started.json()["status"] == "active"

    suspended = client.post(f"/api/v1/programs/{program_id}/suspend")
    assert suspended.status_code == 200
    assert suspended.json()["status"] == "paused"

    restarted = client.post(
        f"/api/v1/programs/{program_id}/start",
        json={"remark": "重新启动项目集"},
    )
    assert restarted.status_code == 200
    assert restarted.json()["status"] == "active"

    history = client.get(f"/api/v1/programs/{program_id}/status-operations")
    assert history.status_code == 200
    history_data = history.json()
    assert any(item["action"] == "start" and item["remark"] == "重新启动项目集" for item in history_data)

    deleted = client.delete(f"/api/v1/programs/{program_id}")
    assert deleted.status_code == 204

    listed = client.get("/api/v1/programs")
    assert all(item["id"] != program_id for item in listed.json())


def test_program_status_options_are_served_by_backend(client: TestClient):
    response = client.get("/api/v1/programs/status-options")

    assert response.status_code == 200
    options = response.json()
    assert {"label": "已挂起", "value": "paused"} in options
    assert {"label": "长期维护", "value": "maintenance"} not in options


def test_project_crud_uses_prd_fields(client: TestClient):
    name = f"项目-{uuid4().hex[:8]}"

    created = client.post(
        "/api/v1/projects",
        json={
            "name": name,
            "end_date": "2026-12-31",
            "actual_start_date": "2026-07-01",
            "actual_end_date": "2026-11-30",
            "description": "项目 API 创建",
        },
    )
    assert created.status_code == 200
    project_id = created.json()["id"]
    assert created.json()["name"] == name
    assert created.json()["end_date"] == "2026-12-31"
    assert created.json()["actual_start_date"] == "2026-07-01"
    assert created.json()["actual_end_date"] == "2026-11-30"
    assert created.json()["is_long_term"] is False
    assert "status" not in created.json()
    assert created.json()["state_category"] == "start"
    assert "owner_id" in created.json()

    detail = client.get(f"/api/v1/projects/{project_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == project_id
    assert detail.json()["name"] == name

    updated = client.patch(f"/api/v1/projects/{project_id}", json={"description": "已更新", "is_long_term": True, "actual_end_date": "2026-12-15"})
    assert updated.status_code == 200
    assert updated.json()["description"] == "已更新"
    assert updated.json()["is_long_term"] is True
    assert updated.json()["end_date"] is None
    assert updated.json()["actual_end_date"] == "2026-12-15"

    started = client.post(
        f"/api/v1/projects/{project_id}/start",
        json={"effective_time": "2026-07-01T09:00:00"},
    )
    assert started.status_code == 200
    assert "status" not in started.json()
    assert started.json()["state_category"] == "normal"

    suspended = client.post(
        f"/api/v1/projects/{project_id}/suspend",
        json={"effective_time": "2026-06-10T11:32:50", "remark": "阶段性挂起"},
    )
    assert suspended.status_code == 200
    assert "status" not in suspended.json()
    assert suspended.json()["state_category"] == "normal"

    restarted = client.post(f"/api/v1/projects/{project_id}/start")
    assert restarted.status_code == 200
    assert "status" not in restarted.json()
    assert restarted.json()["state_category"] == "normal"

    paused_again = client.post(f"/api/v1/projects/{project_id}/suspend")
    assert paused_again.status_code == 200
    assert "status" not in paused_again.json()
    assert paused_again.json()["state_category"] == "normal"

    closed = client.post(
        f"/api/v1/projects/{project_id}/close",
        json={"effective_time": "2026-07-10T18:00:00"},
    )
    assert closed.status_code == 200
    assert "status" not in closed.json()
    assert closed.json()["state_category"] == "terminal"

    activated = client.post(f"/api/v1/projects/{project_id}/activate")
    assert activated.status_code == 200
    assert "status" not in activated.json()
    assert activated.json()["state_category"] == "normal"

    history = client.get(f"/api/v1/projects/{project_id}/status-operations")
    assert history.status_code == 200
    assert any(item["action"] == "suspend" and item["remark"] == "阶段性挂起" for item in history.json())

    deleted = client.delete(f"/api/v1/projects/{project_id}")
    assert deleted.status_code == 204


def test_project_without_assignee_rule_leaves_default_assignees_empty(client: TestClient):
    db = SessionLocal()
    try:
        users = []
        for username in ["product_owner_api", "default_developer_api", "default_tester_api"]:
            user = User(
                username=f"{username}_{uuid4().hex[:6]}",
                full_name=username,
                password_hash=get_password_hash("User123456"),
                is_active=True,
            )
            db.add(user)
            db.flush()
            users.append(user)
        db.commit()
        product_owner_id, developer_id, tester_id = [user.id for user in users]
    finally:
        db.close()

    project = client.post("/api/v1/projects", json={"name": f"Team Defaults Project-{uuid4().hex[:8]}"}).json()
    project_id = project["id"]

    saved_members = client.put(
        f"/api/v1/projects/{project_id}/members",
        json=[
            {"user_id": product_owner_id, "project_role": "product_owner", "is_default_assignee": True, "sort_order": 0},
            {"user_id": developer_id, "project_role": "developer", "sort_order": 1},
            {"user_id": tester_id, "project_role": "tester", "sort_order": 2},
        ],
    )
    assert saved_members.status_code == 200
    members = saved_members.json()
    assert {item["project_role"] for item in members} == {"product_owner", "developer", "tester"}

    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": "Requirement has no default owner"},
    ).json()
    assert requirement["owner_id"] is None

    standalone_task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "title": "Standalone task has no default owner"},
    ).json()
    assert standalone_task["owner_id"] is None

    requirement_task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "requirement_id": requirement["id"], "title": "Requirement task has no default owner"},
    ).json()
    assert requirement_task["owner_id"] is None

    test_case = client.post(
        "/api/v1/test-cases",
        json={"project_id": project_id, "requirement_id": requirement["id"], "title": "Case has no default tester"},
    ).json()
    assert test_case["default_tester_id"] is None

    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "requirement_id": requirement["id"], "title": "Bug has no default owner"},
    ).json()
    assert bug["owner_id"] is None

    generated_task = client.post(
        "/api/v1/tasks/linked",
        json={
            "source_type": "requirement",
            "source_id": requirement["id"],
            "title": "Generated task has no default owner",
        },
    ).json()
    assert generated_task["owner_id"] is None


def test_project_workflow_scheme_does_not_drive_work_item_current_handlers(client: TestClient):
    db = SessionLocal()
    try:
        users = []
        for username in ["rule_product_api", "rule_developer_api", "rule_tester_api"]:
            user = User(
                username=f"{username}_{uuid4().hex[:6]}",
                full_name=username,
                password_hash=get_password_hash("User123456"),
                is_active=True,
            )
            db.add(user)
            db.flush()
            users.append(user)
        db.commit()
        product_owner_id, developer_id, tester_id = [user.id for user in users]
    finally:
        db.close()

    config = client.post(
        "/api/v1/assignee-rule-configs",
        json={
            "name": f"测试责任人规则-{uuid4().hex[:8]}",
            "requirement_owner_roles": "tester",
            "task_owner_roles": "product_owner",
            "test_case_tester_roles": "developer",
            "test_run_owner_roles": "tester",
            "bug_owner_roles": "product_owner",
        },
    ).json()
    _configure_and_enable_scheme(client, config["id"])
    project = client.post(
        "/api/v1/projects",
        json={"name": f"Rule Defaults Project-{uuid4().hex[:8]}", "assignee_rule_config_id": config["id"]},
    ).json()
    project_id = project["id"]
    assert project["assignee_rule_config_id"] == config["id"]

    saved_members = client.put(
        f"/api/v1/projects/{project_id}/members",
        json=[
            {"user_id": product_owner_id, "project_role": "product_owner", "sort_order": 0},
            {"user_id": developer_id, "project_role": "developer", "sort_order": 1},
            {"user_id": tester_id, "project_role": "tester", "sort_order": 2},
        ],
    )
    assert saved_members.status_code == 200

    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": "Requirement has no current handler from scheme"},
    ).json()
    assert requirement["owner_id"] is None

    standalone_task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "title": "Task has no current handler from scheme"},
    ).json()
    assert standalone_task["owner_id"] is None

    test_case = client.post(
        "/api/v1/test-cases",
        json={"project_id": project_id, "title": "Case uses configured developer"},
    ).json()
    assert test_case["default_tester_id"] == developer_id

    test_run = client.post(
        "/api/v1/test-runs",
        json={"project_id": project_id, "name": "Test run uses configured tester"},
    ).json()
    assert test_run["test_owner_id"] == tester_id

    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "title": "Bug has no current handler from scheme"},
    ).json()
    assert bug["owner_id"] is None

    failed_execution = client.post(
        f"/api/v1/test-cases/{test_case['id']}/executions",
        json={"steps_result_json": [{"step": "submit", "expected": "ok", "result": "failed", "actual": "error"}]},
    )
    assert failed_execution.status_code == 200
    bug_from_case = client.post(
        f"/api/v1/test-cases/{test_case['id']}/bugs",
        json={"title": "Bug from failed case has no current handler from scheme"},
    ).json()
    assert bug_from_case["owner_id"] is None

    generated_task = client.post(
        "/api/v1/tasks/linked",
        json={
            "source_type": "requirement",
            "source_id": requirement["id"],
            "title": "Generated task has no current handler from scheme",
        },
    ).json()
    assert generated_task["owner_id"] is None

    updated = client.patch(f"/api/v1/projects/{project_id}", json={"assignee_rule_config_id": None})
    assert updated.status_code == 200
    assert updated.json()["assignee_rule_config_id"] is None


def test_project_update_records_only_changed_fields(client: TestClient):
    db = SessionLocal()
    try:
        user = User(
            username=f"project.audit.{uuid4().hex[:6]}",
            full_name="Project Auditor",
            password_hash=get_password_hash("User123456"),
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_access_token(user.username)
        actor_id = user.id
    finally:
        db.close()

        project = client.post(
            "/api/v1/projects",
            json={
                "name": f"编辑记录项目-{uuid4().hex[:8]}",
                "description": "原描述",
                "start_date": "2026-07-01",
                "owner_id": actor_id,
            },
        ).json()
    project_id = project["id"]

    updated = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "编辑后项目", "description": "原描述", "start_date": "2026-07-02"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert updated.status_code == 200

    logs = client.get(f"/api/v1/projects/{project_id}/audit-logs")
    assert logs.status_code == 200
    data = logs.json()
    assert len(data) == 1
    assert data[0]["action"] == "update"
    assert data[0]["object_type"] == "project"
    assert data[0]["object_id"] == project_id
    assert data[0]["actor_id"] == actor_id
    assert data[0]["actor_name"] == "Project Auditor"
    assert data[0]["before_data"] == {"name": project["name"], "start_date": "2026-07-01"}
    assert data[0]["after_data"] == {"name": "编辑后项目", "start_date": "2026-07-02"}

    unchanged = client.patch(f"/api/v1/projects/{project_id}", json={"name": "编辑后项目"})
    assert unchanged.status_code == 200
    assert len(client.get(f"/api/v1/projects/{project_id}/audit-logs").json()) == 1


def test_project_can_create_child_project_and_inherit_program(client: TestClient):
    program = client.post("/api/v1/programs", json={"name": f"子项目项目集-{uuid4().hex[:8]}"}).json()
    parent = client.post(
        "/api/v1/projects",
        json={"name": f"父项目-{uuid4().hex[:8]}", "program_id": program["id"]},
    ).json()

    child_response = client.post(
        "/api/v1/projects",
        json={"name": f"子项目-{uuid4().hex[:8]}", "parent_id": parent["id"]},
    )

    assert child_response.status_code == 200
    child = child_response.json()
    assert child["parent_id"] == parent["id"]
    assert child["program_id"] == program["id"]

    invalid = client.patch(f"/api/v1/projects/{parent['id']}", json={"parent_id": parent["id"]})
    assert invalid.status_code == 400
    assert invalid.json()["detail"] == "项目不能选择自身作为上级项目"

    cycle = client.patch(f"/api/v1/projects/{parent['id']}", json={"parent_id": child["id"]})
    assert cycle.status_code == 400
    assert cycle.json()["detail"] == "项目不能选择下级项目作为上级项目"


def test_project_iteration_list_exposes_workflow_state_identity(client: TestClient):
    project = client.post("/api/v1/projects", json={"name": f"迭代状态项目-{uuid4().hex[:8]}"}).json()
    iteration = client.post(
        "/api/v1/iterations",
        json={"project_ids": [project["id"]], "name": f"项目迭代状态-{uuid4().hex[:8]}"},
    ).json()

    response = client.get(f"/api/v1/projects/{project['id']}/iterations")

    assert response.status_code == 200
    listed = next(item for item in response.json()["items"] if item["id"] == iteration["id"])
    assert listed["is_requirement_pool"] is False
    assert {
        "workflow_definition_id": listed.get("workflow_definition_id"),
        "current_state_id": listed.get("current_state_id"),
        "status_name": listed.get("status_name"),
        "state_category": listed.get("state_category"),
    } == {
        "workflow_definition_id": iteration["workflow_definition_id"],
        "current_state_id": iteration["current_state_id"],
        "status_name": iteration["status_name"],
        "state_category": iteration["state_category"],
    }


def test_project_delete_cascades_project_tree_work_items_and_iterations(client: TestClient):
    parent = client.post("/api/v1/projects", json={"name": f"级联删除父项目-{uuid4().hex[:8]}"}).json()
    child = client.post(
        "/api/v1/projects",
        json={"name": f"级联删除子项目-{uuid4().hex[:8]}", "parent_id": parent["id"]},
    ).json()
    iteration = client.post(
        "/api/v1/iterations",
        json={"project_ids": [parent["id"], child["id"]], "name": f"级联删除迭代-{uuid4().hex[:8]}"},
    ).json()
    parent_requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": parent["id"], "iteration_id": iteration["id"], "title": "父项目需求随项目删除"},
    ).json()
    child_requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": child["id"], "iteration_id": iteration["id"], "title": "子项目需求随项目删除"},
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": child["id"], "requirement_id": child_requirement["id"], "title": "子项目任务随项目删除"},
    ).json()
    case = client.post(
        "/api/v1/test-cases",
        json={"project_id": child["id"], "requirement_id": child_requirement["id"], "title": "子项目用例随项目删除"},
    ).json()
    client.post(
        f"/api/v1/test-cases/{case['id']}/executions",
        json={
            "steps_result_json": [
                {"step": "open page", "expected": "page shown", "result": "passed", "actual": "page shown"}
            ]
        },
    )
    test_run = client.post(
        "/api/v1/test-runs",
        json={"project_id": child["id"], "iteration_id": iteration["id"], "name": "子项目测试单随项目删除"},
    ).json()
    selected = client.post(
        f"/api/v1/test-runs/{test_run['id']}/cases",
        json={"test_case_ids": [case["id"]]},
    ).json()
    bug = client.post(
        "/api/v1/bugs",
        json={
            "project_id": child["id"],
            "iteration_id": iteration["id"],
            "requirement_id": child_requirement["id"],
            "task_id": task["id"],
            "test_case_id": case["id"],
            "test_run_id": test_run["id"],
            "title": "子项目Bug随项目删除",
        },
    ).json()

    deleted = client.delete(f"/api/v1/projects/{parent['id']}")

    assert deleted.status_code == 204
    assert client.get(f"/api/v1/projects/{parent['id']}").status_code == 404
    assert client.get(f"/api/v1/projects/{child['id']}").status_code == 404
    assert client.get(f"/api/v1/requirements/{parent_requirement['id']}").status_code == 404
    assert client.get(f"/api/v1/requirements/{child_requirement['id']}").status_code == 404
    assert client.get(f"/api/v1/tasks/{task['id']}").status_code == 404
    assert client.get(f"/api/v1/test-cases/{case['id']}").status_code == 404
    assert client.get(f"/api/v1/bugs/{bug['id']}").status_code == 404
    assert iteration["id"] not in {item["id"] for item in client.get("/api/v1/iterations").json()}
    assert test_run["id"] not in {item["id"] for item in client.get("/api/v1/test-runs").json()}
    assert selected[0]["id"] not in {item["id"] for item in client.get("/api/v1/test-run-cases").json()}
    assert client.get(f"/api/v1/test-cases/{case['id']}/executions").status_code == 404



def test_project_delete_keeps_shared_iteration_and_removes_deleted_project_scope(client: TestClient):
    deleted_project = client.post("/api/v1/projects", json={"name": f"Shared Delete Project-{uuid4().hex[:8]}"}).json()
    kept_project = client.post("/api/v1/projects", json={"name": f"Shared Keep Project-{uuid4().hex[:8]}"}).json()
    iteration = client.post(
        "/api/v1/iterations",
        json={"project_ids": [deleted_project["id"], kept_project["id"]], "name": f"Shared Iteration-{uuid4().hex[:8]}"},
    ).json()
    deleted_requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": deleted_project["id"], "iteration_id": iteration["id"], "title": "Deleted project requirement"},
    ).json()
    kept_requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": kept_project["id"], "iteration_id": iteration["id"], "title": "Kept project requirement"},
    ).json()

    deleted = client.delete(f"/api/v1/projects/{deleted_project['id']}")

    assert deleted.status_code == 204
    listed_iterations = client.get("/api/v1/iterations").json()
    kept_iteration = next(item for item in listed_iterations if item["id"] == iteration["id"])
    assert kept_iteration["project_ids"] == [kept_project["id"]]
    assert client.get(f"/api/v1/requirements/{deleted_requirement['id']}").status_code == 404
    assert client.get(f"/api/v1/requirements/{kept_requirement['id']}").status_code == 200

def test_open_project_move_only_changes_parent(client: TestClient):
    parent = client.post("/api/v1/projects", json={"name": f"父项目-{uuid4().hex[:8]}"}).json()
    project = client.post("/api/v1/projects", json={"name": f"移动项目-{uuid4().hex[:8]}"}).json()
    client.post(f"/api/v1/projects/{project['id']}/start", json={"effective_time": "2026-06-01T09:00:00"})

    moved = client.patch(f"/api/v1/projects/{project['id']}", json={"parent_id": parent["id"]})

    assert moved.status_code == 200
    assert moved.json()["parent_id"] == parent["id"]
    assert "status" not in moved.json()
    assert moved.json()["state_category"] == "normal"


def test_closed_project_move_only_changes_parent_after_phase_removed(client: TestClient):
    parent = client.post("/api/v1/projects", json={"name": f"最终规则父项目-{uuid4().hex[:8]}"}).json()
    project = client.post("/api/v1/projects", json={"name": f"最终规则子项目-{uuid4().hex[:8]}"}).json()
    development_requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "title": f"转移前需求-{uuid4().hex[:8]}"},
    ).json()
    development_task = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "title": f"转移前任务-{uuid4().hex[:8]}"},
    ).json()
    client.post(f"/api/v1/projects/{project['id']}/start", json={"effective_time": "2026-06-01T09:00:00"})
    blocked_close = client.post(f"/api/v1/projects/{project['id']}/close", json={"effective_time": "2026-06-10T18:00:00"})
    assert blocked_close.status_code == 400

    moved = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={
            "parent_id": parent["id"],
            "maintenance_start_time": "2026-06-11T09:30:00",
            "maintenance_remark": "legacy payload should be ignored",
        },
    )

    assert moved.status_code == 200
    assert moved.json()["parent_id"] == parent["id"]
    assert "status" not in moved.json()
    assert moved.json()["state_category"] == "normal"
    assert "lifecycle_phase" not in moved.json()
    assert "maintenance_start_time" not in moved.json()
    assert client.get(f"/api/v1/requirements/{development_requirement['id']}").status_code == 200
    assert client.get(f"/api/v1/tasks/{development_task['id']}").status_code == 200

    history = client.get(f"/api/v1/projects/{project['id']}/status-operations").json()
    assert all(item["action"] != "move_to_maintenance" for item in history)


def test_dashboard_summary_reads_database_counts(client: TestClient):
    response = client.get("/api/v1/dashboard/summary")

    assert response.status_code == 200
    data = response.json()
    assert {"programs", "projects", "requirements", "tasks", "open_bugs"} <= set(data)
    assert isinstance(data["projects"], int)


def test_project_requirement_list_filters_by_current_state_id(client: TestClient):
    project = client.post("/api/v1/projects", json={"name": f"状态筛选项目-{uuid4().hex[:8]}"}).json()
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "title": "按节点 ID 筛选的需求"},
    ).json()

    matched = client.get(
        f"/api/v1/projects/{project['id']}/requirements",
        params={"current_state_id": requirement["current_state_id"]},
    )
    unmatched = client.get(
        f"/api/v1/projects/{project['id']}/requirements",
        params={"current_state_id": requirement["current_state_id"] + 999999},
    )

    assert matched.status_code == 200
    assert requirement["id"] in {item["id"] for item in matched.json()["items"]}
    assert unmatched.status_code == 200
    assert requirement["id"] not in {item["id"] for item in unmatched.json()["items"]}


def test_project_close_gate_uses_work_item_state_category(client: TestClient):
    project = client.post("/api/v1/projects", json={"name": f"终态门禁项目-{uuid4().hex[:8]}"}).json()
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "title": "终态门禁需求"},
    ).json()
    db = SessionLocal()
    try:
        stored = db.query(Requirement).filter(Requirement.id == requirement["id"]).first()
        terminal = WorkflowState(
            definition_id=stored.workflow_definition_id,
            status_name="业务已结束",
            category="terminal",
            enabled=True,
        )
        db.add(terminal)
        db.flush()
        stored.current_state_id = terminal.id
        db.commit()
    finally:
        db.close()

    assert client.post(
        f"/api/v1/projects/{project['id']}/start",
        json={"effective_time": "2026-07-01T09:00:00"},
    ).status_code == 200
    closed = client.post(
        f"/api/v1/projects/{project['id']}/close",
        json={"effective_time": "2026-07-15T18:00:00"},
    )

    assert closed.status_code == 200, closed.text


def test_program_tree_contains_child_programs_and_bound_projects(client: TestClient):
    parent = client.post("/api/v1/programs", json={"name": f"父项目集-{uuid4().hex[:8]}"}).json()
    child = client.post(
        "/api/v1/programs",
        json={"name": f"子项目集-{uuid4().hex[:8]}", "parent_id": parent["id"]},
    ).json()
    project = client.post(
        "/api/v1/projects",
        json={"name": f"绑定项目-{uuid4().hex[:8]}", "program_id": child["id"]},
    ).json()

    response = client.get("/api/v1/programs/tree")

    assert response.status_code == 200
    parent_node = next(item for item in response.json() if item["id"] == parent["id"])
    child_node = next(item for item in parent_node["children"] if item["id"] == child["id"])
    project_node = next(item for item in child_node["projects"] if item["id"] == project["id"])
    assert project_node["name"] == project["name"]
    assert {
        "workflow_definition_id": project_node.get("workflow_definition_id"),
        "current_state_id": project_node.get("current_state_id"),
        "status_name": project_node.get("status_name"),
        "state_category": project_node.get("state_category"),
    } == {
        "workflow_definition_id": project["workflow_definition_id"],
        "current_state_id": project["current_state_id"],
        "status_name": project["status_name"],
        "state_category": project["state_category"],
    }


def test_program_tree_contains_unbound_projects_as_top_level_nodes(client: TestClient):
    project = client.post(
        "/api/v1/projects",
        json={"name": f"独立项目-{uuid4().hex[:8]}"},
    ).json()

    response = client.get("/api/v1/programs/tree")

    assert response.status_code == 200
    project_node = next(item for item in response.json() if item["id"] == project["id"] and item.get("node_type") == "project")
    assert project_node["name"] == project["name"]
    assert {
        "workflow_definition_id": project_node.get("workflow_definition_id"),
        "current_state_id": project_node.get("current_state_id"),
        "status_name": project_node.get("status_name"),
        "state_category": project_node.get("state_category"),
    } == {
        "workflow_definition_id": project["workflow_definition_id"],
        "current_state_id": project["current_state_id"],
        "status_name": project["status_name"],
        "state_category": project["state_category"],
    }


def test_project_start_activates_parent_program(client: TestClient):
    parent_program = client.post("/api/v1/programs", json={"name": f"同步父项目集-{uuid4().hex[:8]}"}).json()
    program = client.post(
        "/api/v1/programs",
        json={"name": f"同步项目集-{uuid4().hex[:8]}", "parent_id": parent_program["id"]},
    ).json()
    project = client.post(
        "/api/v1/projects",
        json={"name": f"同步项目-{uuid4().hex[:8]}", "program_id": program["id"]},
    ).json()

    response = client.post(
        f"/api/v1/projects/{project['id']}/start",
        json={"effective_time": "2026-06-01T09:00:00"},
    )

    assert response.status_code == 200
    assert "status" not in response.json()
    assert response.json()["state_category"] == "normal"
    programs = client.get("/api/v1/programs").json()
    synced_program = next(item for item in programs if item["id"] == program["id"])
    synced_parent_program = next(item for item in programs if item["id"] == parent_program["id"])
    assert synced_program["status"] == "active"
    assert synced_program["actual_start_date"] == "2026-06-01"
    assert synced_parent_program["status"] == "active"
    assert synced_parent_program["actual_start_date"] == "2026-06-01"


def test_project_status_dates_follow_action_rules(client: TestClient):
    project = client.post(
        "/api/v1/projects",
        json={"name": f"项目状态日期-{uuid4().hex[:8]}"},
    ).json()

    missing_start = client.post(f"/api/v1/projects/{project['id']}/start", json={"remark": "no date"})
    assert missing_start.status_code == 400

    started = client.post(
        f"/api/v1/projects/{project['id']}/start",
        json={"effective_time": "2026-06-01T09:00:00", "remark": "start"},
    )
    assert started.status_code == 200
    assert started.json()["actual_start_date"] == "2026-06-01"

    client.post(f"/api/v1/projects/{project['id']}/suspend", json={"remark": "pause"})
    restarted = client.post(f"/api/v1/projects/{project['id']}/start", json={"remark": "resume"})
    assert restarted.status_code == 200
    assert restarted.json()["actual_start_date"] == "2026-06-01"

    missing_close = client.post(f"/api/v1/projects/{project['id']}/close", json={"remark": "no date"})
    assert missing_close.status_code == 400

    closed = client.post(
        f"/api/v1/projects/{project['id']}/close",
        json={"effective_time": "2026-06-08T18:30:00", "remark": "close"},
    )
    assert closed.status_code == 200
    assert closed.json()["actual_end_date"] == "2026-06-08"


def test_project_status_history_uses_authenticated_user_name(client: TestClient):
    db = SessionLocal()
    try:
        user = User(
            username=f"bob.actor.{uuid4().hex[:6]}",
            full_name="Bob",
            password_hash=get_password_hash("User123456"),
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_access_token(user.username)
    finally:
        db.close()

        project = client.post(
            "/api/v1/projects",
            json={"name": f"真实操作人项目-{uuid4().hex[:8]}", "owner_id": user.id},
        ).json()

    started = client.post(
        f"/api/v1/projects/{project['id']}/start",
        json={"effective_time": "2026-06-01T09:00:00"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert started.status_code == 200
    history = client.get(f"/api/v1/projects/{project['id']}/status-operations").json()
    assert history[-1]["action"] == "start"
    assert history[-1]["actor_name"] == "Bob"


def test_program_status_dates_follow_action_rules(client: TestClient):
    program = client.post(
        "/api/v1/programs",
        json={"name": f"项目集状态日期-{uuid4().hex[:8]}"},
    ).json()

    missing_start = client.post(f"/api/v1/programs/{program['id']}/start", json={"remark": "no date"})
    assert missing_start.status_code == 400

    started = client.post(
        f"/api/v1/programs/{program['id']}/start",
        json={"effective_time": "2026-06-02T09:00:00", "remark": "start"},
    )
    assert started.status_code == 200
    assert started.json()["actual_start_date"] == "2026-06-02"

    client.post(f"/api/v1/programs/{program['id']}/suspend", json={"remark": "pause"})
    restarted = client.post(f"/api/v1/programs/{program['id']}/start", json={"remark": "resume"})
    assert restarted.status_code == 200
    assert restarted.json()["actual_start_date"] == "2026-06-02"

    missing_close = client.post(f"/api/v1/programs/{program['id']}/close", json={"remark": "no date"})
    assert missing_close.status_code == 400

    closed = client.post(
        f"/api/v1/programs/{program['id']}/close",
        json={"effective_time": "2026-06-09T18:30:00", "remark": "close"},
    )
    assert closed.status_code == 200
    assert closed.json()["actual_end_date"] == "2026-06-09"


def test_closing_program_blocks_when_descendants_are_not_closed(client: TestClient):
    parent = client.post("/api/v1/programs", json={"name": f"关闭父项目集-{uuid4().hex[:8]}"}).json()
    child = client.post(
        "/api/v1/programs",
        json={"name": f"关闭子项目集-{uuid4().hex[:8]}", "parent_id": parent["id"]},
    ).json()
    client.post(f"/api/v1/programs/{parent['id']}/start", json={"effective_time": "2026-06-01T09:00:00"})

    blocked = client.post(f"/api/v1/programs/{parent['id']}/close")

    assert blocked.status_code == 400
    assert blocked.json()["detail"] == "存在子项目集或项目为未关闭状态"

    client.post(f"/api/v1/programs/{child['id']}/start", json={"effective_time": "2026-06-01T09:00:00"})
    client.post(f"/api/v1/programs/{child['id']}/close", json={"effective_time": "2026-06-02T18:00:00"})
    closed = client.post(f"/api/v1/programs/{parent['id']}/close", json={"effective_time": "2026-06-03T18:00:00"})

    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
