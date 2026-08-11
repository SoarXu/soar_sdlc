from datetime import datetime, timedelta
from unittest.mock import Mock
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.session import SessionLocal
from app.models.bug import Bug
from app.models.iteration import Iteration
from app.models.object_watch import ObjectWatch
from app.models.project_member import ProjectMember
from app.models.requirement import Requirement
from app.models.role import Role, UserRole
from app.models.task import Task
from app.models.user import User
from app.models.workflow_definition import WorkflowDefinition, WorkflowState, WorkflowTransition
from app.models.work_item_comment import WorkItemComment
from app.services.dashboard_service import _terminal_iteration_open_item_refs


def _create_user_with_role(username: str, role_key: str) -> tuple[int, str]:
    db = SessionLocal()
    try:
        role = db.query(Role).filter(Role.role_key == role_key).first()
        if not role:
            role = Role(role_key=role_key, role_name=role_key, enabled=True, is_system=True)
            db.add(role)
            db.flush()
        user = User(
            username=username,
            full_name=username,
            password_hash=get_password_hash("User123456"),
            is_active=True,
        )
        db.add(user)
        db.flush()
        db.add(UserRole(user_id=user.id, role_id=role.id))
        db.commit()
        return user.id, create_access_token(user.username)
    finally:
        db.close()


def _create_project(client: TestClient, name: str | None = None) -> int:
    response = client.post("/api/v1/projects", json={"name": name or f"Project-{uuid4().hex[:8]}"})
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


def _start_iteration(client: TestClient, iteration_id: int) -> None:
    response = client.post(
        f"/api/v1/workflow-runtime/iteration/{iteration_id}/transition",
        json={"action_key": "start", "payload": {"effective_time": "2026-06-24T10:00:00"}},
    )
    assert response.status_code == 200


def test_workbench_project_scope_does_not_expand_between_parent_and_child(client: TestClient):
    parent_member_id, parent_token = _create_user_with_role(f"parent_scope_{uuid4().hex[:6]}", "developer")
    child_member_id, child_token = _create_user_with_role(f"child_scope_{uuid4().hex[:6]}", "developer")
    parent_id = _create_project(client, "Isolated parent")
    child = client.post("/api/v1/projects", json={"name": "Isolated child", "parent_id": parent_id}).json()
    parent_iteration = _create_iteration(client, parent_id, "Parent active")
    child_iteration = _create_iteration(client, child["id"], "Child active")
    _start_iteration(client, parent_iteration)
    _start_iteration(client, child_iteration)
    parent_task = client.post("/api/v1/tasks", json={"project_id": parent_id, "iteration_id": parent_iteration, "title": "Parent only"}).json()
    child_task = client.post("/api/v1/tasks", json={"project_id": child["id"], "iteration_id": child_iteration, "title": "Child only"}).json()
    _add_project_member(parent_id, parent_member_id, "developer")
    _add_project_member(child["id"], child_member_id, "developer")

    parent_items = client.get("/api/v1/dashboard/workbench", headers={"Authorization": f"Bearer {parent_token}"}).json()["unassigned"]["items"]
    child_items = client.get("/api/v1/dashboard/workbench", headers={"Authorization": f"Bearer {child_token}"}).json()["unassigned"]["items"]

    assert {item["id"] for item in parent_items if item["object_type"] == "task"} >= {parent_task["id"]}
    assert child_task["id"] not in {item["id"] for item in parent_items}
    assert {item["id"] for item in child_items if item["object_type"] == "task"} >= {child_task["id"]}
    assert parent_task["id"] not in {item["id"] for item in child_items}


def test_workbench_returns_default_queue_sections_for_pending_and_unassigned(client: TestClient):
    developer_id, developer_token = _create_user_with_role(f"queue_user_{uuid4().hex[:6]}", "developer")
    project_id = _create_project(client, "Queue workbench project")
    iteration_id = _create_iteration(client, project_id, "Queue iteration")
    _start_iteration(client, iteration_id)
    owned_task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
            "title": "Owned queue task",
            "owner_id": developer_id,
        },
    ).json()
    unassigned_bug = client.post(
        "/api/v1/bugs",
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
            "title": "Unassigned queue bug",
        },
    ).json()

    db = SessionLocal()
    try:
        db.add(
            ProjectMember(
                project_id=project_id,
                user_id=developer_id,
                project_role="developer",
                is_workbench_participant=True,
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/api/v1/dashboard/workbench",
        headers={"Authorization": f"Bearer {developer_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["pending_handling"]["label"] == "待处理"
    pending_items = {item["id"]: item for item in data["pending_handling"]["items"]}
    assert owned_task["id"] in pending_items
    assert pending_items[owned_task["id"]]["iteration_id"] == iteration_id
    assert pending_items[owned_task["id"]]["iteration_name"] == "Queue iteration"
    assert data["unassigned"]["label"] == "未分派"
    assert unassigned_bug["id"] in {item["id"] for item in data["unassigned"]["items"]}
    assert "project_board" not in data
    assert "iterations" not in data


def test_workbench_returns_each_visible_in_progress_iteration_item_once(client: TestClient):
    user_id, token = _create_user_with_role(f"canonical_workbench_{uuid4().hex[:6]}", "developer")
    collaborator_id, _ = _create_user_with_role(f"canonical_collaborator_{uuid4().hex[:6]}", "developer")
    visible_project_id = _create_project(client, f"Canonical visible project {uuid4().hex[:6]}")
    invisible_project_id = _create_project(client, f"Canonical invisible project {uuid4().hex[:6]}")
    active_iteration_id = _create_iteration(client, visible_project_id, "Canonical active iteration")
    planning_iteration_id = _create_iteration(client, visible_project_id, "Canonical planning iteration")
    custom_in_progress_iteration_id = _create_iteration(client, visible_project_id, "Canonical custom in-progress iteration")
    custom_normal_iteration_id = _create_iteration(client, visible_project_id, "Canonical custom normal iteration")
    paused_iteration_id = _create_iteration(client, visible_project_id, "Canonical paused iteration")
    invisible_iteration_id = _create_iteration(client, invisible_project_id, "Canonical invisible iteration")
    _start_iteration(client, active_iteration_id)
    _start_iteration(client, invisible_iteration_id)
    _add_project_member(visible_project_id, user_id, "developer")
    _add_project_member(visible_project_id, collaborator_id, "developer")

    active_requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": visible_project_id,
            "iteration_id": active_iteration_id,
            "title": "Visible active requirement",
            "owner_id": collaborator_id,
        },
    ).json()
    active_completed_task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": visible_project_id,
            "iteration_id": active_iteration_id,
            "title": "Visible completed task",
            "owner_id": collaborator_id,
        },
    ).json()
    active_cancelled_bug = client.post(
        "/api/v1/bugs",
        json={
            "project_id": visible_project_id,
            "iteration_id": active_iteration_id,
            "title": "Visible cancelled bug",
            "owner_id": collaborator_id,
        },
    ).json()
    planning_requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": visible_project_id, "iteration_id": planning_iteration_id, "title": "Planning requirement"},
    ).json()
    planning_task = client.post(
        "/api/v1/tasks",
        json={"project_id": visible_project_id, "iteration_id": planning_iteration_id, "title": "Planning task"},
    ).json()
    planning_bug = client.post(
        "/api/v1/bugs",
        json={"project_id": visible_project_id, "iteration_id": planning_iteration_id, "title": "Planning bug"},
    ).json()
    custom_in_progress_requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": visible_project_id,
            "iteration_id": custom_in_progress_iteration_id,
            "title": "Custom in-progress requirement",
        },
    ).json()
    custom_normal_requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": visible_project_id,
            "iteration_id": custom_normal_iteration_id,
            "title": "Custom normal requirement",
        },
    ).json()
    paused_task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": visible_project_id,
            "iteration_id": paused_iteration_id,
            "title": "Paused task with terminal transitions",
        },
    ).json()
    invisible_requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": invisible_project_id, "iteration_id": invisible_iteration_id, "title": "Invisible requirement"},
    ).json()
    invisible_task = client.post(
        "/api/v1/tasks",
        json={"project_id": invisible_project_id, "iteration_id": invisible_iteration_id, "title": "Invisible task"},
    ).json()
    invisible_bug = client.post(
        "/api/v1/bugs",
        json={"project_id": invisible_project_id, "iteration_id": invisible_iteration_id, "title": "Invisible bug"},
    ).json()

    db = SessionLocal()
    try:
        def terminal_state(definition_id: int, status_name: str, terminal_kind: str) -> int:
            state = WorkflowState(
                definition_id=definition_id,
                status_name=status_name,
                category="terminal",
                terminal_kind=terminal_kind,
                enabled=True,
            )
            db.add(state)
            db.flush()
            return state.id

        completed_state_id = terminal_state(
            active_completed_task["workflow_definition_id"], "Completed canonical task", "completed"
        )
        cancelled_state_id = terminal_state(
            active_cancelled_bug["workflow_definition_id"], "Cancelled canonical bug", "terminated"
        )
        custom_in_progress_iteration = db.query(Iteration).filter(
            Iteration.id == custom_in_progress_iteration_id
        ).one()
        custom_normal_iteration = db.query(Iteration).filter(Iteration.id == custom_normal_iteration_id).one()
        paused_iteration = db.query(Iteration).filter(Iteration.id == paused_iteration_id).one()
        original_custom_in_progress_state_id = custom_in_progress_iteration.current_state_id
        original_custom_normal_definition_id = custom_normal_iteration.workflow_definition_id
        original_custom_normal_state_id = custom_normal_iteration.current_state_id
        original_paused_state_id = paused_iteration.current_state_id
        custom_in_progress_state = WorkflowState(
            definition_id=custom_in_progress_iteration.workflow_definition_id,
            status_name="Custom in-progress iteration state",
            category="in_progress",
            enabled=True,
        )
        db.add(custom_in_progress_state)
        custom_normal_definition = WorkflowDefinition(
            name="Custom normal iteration workflow",
            object_type="iteration",
            scope_type="project",
            scope_id=visible_project_id,
            template_key=f"custom.iteration.{uuid4().hex[:6]}",
            is_default_template=False,
            enabled=True,
        )
        db.add(custom_normal_definition)
        db.flush()
        custom_normal_start_state = WorkflowState(
            definition_id=custom_normal_definition.id,
            status_name="Custom planning",
            category="start",
            enabled=True,
        )
        custom_normal_active_state = WorkflowState(
            definition_id=custom_normal_definition.id,
            status_name="Custom active",
            category="normal",
            enabled=True,
        )
        db.add_all([custom_normal_start_state, custom_normal_active_state])
        db.flush()
        custom_normal_start_transition = WorkflowTransition(
            definition_id=custom_normal_definition.id,
            action_key="start",
            action_name="Start",
            from_state_id=custom_normal_start_state.id,
            to_state_id=custom_normal_active_state.id,
            enabled=True,
        )
        db.add(custom_normal_start_transition)
        paused_state = WorkflowState(
            definition_id=paused_iteration.workflow_definition_id,
            status_name="Paused iteration state",
            category="normal",
            enabled=True,
        )
        db.add(paused_state)
        db.flush()
        custom_in_progress_state_id = custom_in_progress_state.id
        custom_normal_definition_id = custom_normal_definition.id
        custom_normal_state_ids = [custom_normal_start_state.id, custom_normal_active_state.id]
        custom_normal_start_transition_id = custom_normal_start_transition.id
        paused_state_id = paused_state.id
        terminal_state_ids = {
            transition.action_key: transition.to_state_id
            for transition in db.query(WorkflowTransition)
            .filter(
                WorkflowTransition.definition_id == paused_iteration.workflow_definition_id,
                WorkflowTransition.action_key.in_(("complete", "cancel")),
                WorkflowTransition.enabled.is_(True),
            )
            .all()
        }
        paused_transitions = [
            WorkflowTransition(
                definition_id=paused_iteration.workflow_definition_id,
                action_key=action_key,
                action_name=f"Paused {action_key}",
                from_state_id=paused_state_id,
                to_state_id=terminal_state_ids[action_key],
                enabled=True,
            )
            for action_key in ("complete", "cancel")
        ]
        db.add_all(paused_transitions)
        db.flush()
        paused_transition_ids = [transition.id for transition in paused_transitions]
        db.query(Task).filter(Task.id == active_completed_task["id"]).update({"current_state_id": completed_state_id})
        db.query(Bug).filter(Bug.id == active_cancelled_bug["id"]).update({"current_state_id": cancelled_state_id})
        db.query(Iteration).filter(Iteration.id == custom_in_progress_iteration_id).update(
            {"current_state_id": custom_in_progress_state.id}
        )
        db.query(Iteration).filter(Iteration.id == custom_normal_iteration_id).update(
            {
                "workflow_definition_id": custom_normal_definition_id,
                "current_state_id": custom_normal_active_state.id,
            }
        )
        db.query(Iteration).filter(Iteration.id == paused_iteration_id).update({"current_state_id": paused_state_id})
        db.commit()
    finally:
        db.close()

    response = client.get("/api/v1/dashboard/workbench", headers={"Authorization": f"Bearer {token}"})

    db = SessionLocal()
    try:
        db.query(Iteration).filter(Iteration.id == custom_in_progress_iteration_id).update(
            {"current_state_id": original_custom_in_progress_state_id}
        )
        db.query(Iteration).filter(Iteration.id == custom_normal_iteration_id).update(
            {
                "workflow_definition_id": original_custom_normal_definition_id,
                "current_state_id": original_custom_normal_state_id,
            }
        )
        db.query(Iteration).filter(Iteration.id == paused_iteration_id).update(
            {"current_state_id": original_paused_state_id}
        )
        db.query(WorkflowTransition).filter(WorkflowTransition.id.in_(paused_transition_ids)).delete(
            synchronize_session=False
        )
        db.query(WorkflowTransition).filter(WorkflowTransition.id == custom_normal_start_transition_id).delete()
        db.query(WorkflowState).filter(WorkflowState.id == custom_in_progress_state_id).delete()
        db.query(WorkflowState).filter(WorkflowState.id.in_(custom_normal_state_ids)).delete(
            synchronize_session=False
        )
        db.query(WorkflowState).filter(WorkflowState.id == paused_state_id).delete()
        db.query(WorkflowDefinition).filter(WorkflowDefinition.id == custom_normal_definition_id).delete()
        db.commit()
    finally:
        db.close()

    assert response.status_code == 200
    item_refs = [(item["object_type"], item["id"]) for item in response.json()["active_iteration_items"]]
    expected_refs = {
        ("requirement", active_requirement["id"]),
        ("task", active_completed_task["id"]),
        ("bug", active_cancelled_bug["id"]),
        ("requirement", custom_in_progress_requirement["id"]),
        ("requirement", custom_normal_requirement["id"]),
    }
    excluded_refs = {
        ("requirement", planning_requirement["id"]),
        ("task", planning_task["id"]),
        ("bug", planning_bug["id"]),
        ("task", paused_task["id"]),
        ("requirement", invisible_requirement["id"]),
        ("task", invisible_task["id"]),
        ("bug", invisible_bug["id"]),
    }
    assert set(item_refs) == expected_refs
    assert len(item_refs) == len(expected_refs)
    assert excluded_refs.isdisjoint(item_refs)
    assert all(item["update_time"] for item in response.json()["active_iteration_items"])


def test_active_iteration_items_include_due_date_overdue_hours(client: TestClient):
    user_id, token = _create_user_with_role(f"overdue_active_{uuid4().hex[:6]}", "developer")
    project_id = _create_project(client, "Overdue active iteration project")
    iteration_id = _create_iteration(client, project_id, "Overdue active iteration")
    _start_iteration(client, iteration_id)
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": "Overdue task"},
    ).json()
    _add_project_member(project_id, user_id, "developer")

    db = SessionLocal()
    try:
        db.query(Task).filter(Task.id == task["id"]).update(
            {Task.due_date: (datetime.now() - timedelta(days=2)).date()}
        )
        db.commit()
    finally:
        db.close()

    response = client.get("/api/v1/dashboard/workbench", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    items = response.json()["active_iteration_items"]
    overdue_task = next(item for item in items if item["object_type"] == "task" and item["id"] == task["id"])
    assert overdue_task["overdue_hours"] >= 24


def test_workbench_partitions_active_iteration_terminal_items_by_terminal_kind(client: TestClient):
    user_id, token = _create_user_with_role(f"terminal_partition_{uuid4().hex[:6]}", "developer")
    project_id = _create_project(client, "Terminal partition project")
    active_iteration_id = _create_iteration(client, project_id, "Terminal partition active")
    inactive_iteration_id = _create_iteration(client, project_id, "Terminal partition inactive")
    _start_iteration(client, active_iteration_id)
    _add_project_member(project_id, user_id, "developer")
    completed_requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "iteration_id": active_iteration_id, "title": "Completed requirement", "owner_id": user_id},
    ).json()
    terminated_task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "iteration_id": active_iteration_id, "title": "Terminated task", "owner_id": user_id},
    ).json()
    unclassified_bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "iteration_id": active_iteration_id, "title": "Unclassified terminal bug", "owner_id": user_id},
    ).json()
    inactive_task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "iteration_id": inactive_iteration_id, "title": "Inactive terminal task", "owner_id": user_id},
    ).json()

    db = SessionLocal()
    try:
        def terminal_state(definition_id: int, status_name: str, terminal_kind: str | None) -> int:
            state = WorkflowState(
                definition_id=definition_id,
                status_name=status_name,
                category="terminal",
                terminal_kind=terminal_kind,
                enabled=True,
            )
            db.add(state)
            db.flush()
            return state.id

        completed_state_id = terminal_state(completed_requirement["workflow_definition_id"], "Completed partition", "completed")
        terminated_state_id = terminal_state(terminated_task["workflow_definition_id"], "Terminated partition", "terminated")
        unclassified_state_id = terminal_state(unclassified_bug["workflow_definition_id"], "Unclassified partition", None)
        inactive_state_id = terminal_state(inactive_task["workflow_definition_id"], "Inactive partition", "completed")
        db.query(Requirement).filter(Requirement.id == completed_requirement["id"]).update(
            {"current_state_id": completed_state_id}
        )
        db.query(Task).filter(Task.id == terminated_task["id"]).update({"current_state_id": terminated_state_id})
        db.query(Bug).filter(Bug.id == unclassified_bug["id"]).update({"current_state_id": unclassified_state_id})
        db.query(Task).filter(Task.id == inactive_task["id"]).update({"current_state_id": inactive_state_id})
        db.commit()
    finally:
        db.close()

    response = client.get("/api/v1/dashboard/workbench", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    completed = {(item["object_type"], item["id"]): item for item in data["completed"]["items"]}
    terminated = {(item["object_type"], item["id"]): item for item in data["terminated"]["items"]}
    assert completed[("requirement", completed_requirement["id"])]["terminal_kind"] == "completed"
    assert terminated[("task", terminated_task["id"])]["terminal_kind"] == "terminated"
    terminal_refs = set(completed) | set(terminated)
    assert ("bug", unclassified_bug["id"]) not in terminal_refs
    assert ("task", inactive_task["id"]) not in terminal_refs


def test_workbench_queue_uses_state_category_and_status_name(client: TestClient):
    developer_id, developer_token = _create_user_with_role(f"state_queue_{uuid4().hex[:6]}", "developer")
    project_id = _create_project(client, "State identity queue project")
    iteration_id = _create_iteration(client, project_id, "State identity queue iteration")
    _start_iteration(client, iteration_id)
    task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
            "title": "State identity queue task",
            "owner_id": developer_id,
        },
    ).json()
    _add_project_member(project_id, developer_id, "developer")

    db = SessionLocal()
    try:
        stored = db.query(Task).filter(Task.id == task["id"]).first()
        state = db.query(WorkflowState).filter(WorkflowState.id == stored.current_state_id).first()
        renamed_state = WorkflowState(
            definition_id=state.definition_id,
            status_name="等待本人处理",
            category=state.category,
            enabled=True,
        )
        db.add(renamed_state)
        db.flush()
        stored.current_state_id = renamed_state.id
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/api/v1/dashboard/workbench",
        headers={"Authorization": f"Bearer {developer_token}"},
    )

    assert response.status_code == 200
    listed = next(item for item in response.json()["pending_handling"]["items"] if item["id"] == task["id"])
    assert listed["status"] == "等待本人处理"
    assert listed["status_name"] == "等待本人处理"
    assert listed["state_category"] == "start"


def test_workbench_returns_created_watched_mentioned_and_exception_center(client: TestClient):
    developer_id, developer_token = _create_user_with_role(f"follow_user_{uuid4().hex[:6]}", "developer")
    project_id = _create_project(client, "Follow project")
    iteration_id = _create_iteration(client, project_id, "Follow iteration")
    _start_iteration(client, iteration_id)
    created_requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
            "title": "Created requirement",
            "owner_id": developer_id,
        },
    ).json()
    watched_task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
            "title": "Watched task",
        },
    ).json()
    mentioned_bug = client.post(
        "/api/v1/bugs",
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
            "title": "Mentioned bug",
        },
    ).json()
    verified_bug = client.post(
        "/api/v1/bugs",
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
            "title": "Verified not closed bug",
            "owner_id": developer_id,
        },
    ).json()
    overdue_bug = client.post(
        "/api/v1/bugs",
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
            "title": "High priority unprocessed bug",
            "priority": "1",
        },
    ).json()
    watched_test_case = client.post(
        "/api/v1/test-cases",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": "Watched test case"},
    ).json()
    mentioned_test_run = client.post(
        "/api/v1/test-runs",
        json={"project_id": project_id, "iteration_id": iteration_id, "name": "Mentioned test run"},
    ).json()

    db = SessionLocal()
    try:
        db.add(
            ProjectMember(
                project_id=project_id,
                user_id=developer_id,
                project_role="developer",
                is_workbench_participant=True,
            )
        )
        verified_state_id = db.query(WorkflowTransition.to_state_id).filter(
            WorkflowTransition.definition_id == verified_bug["workflow_definition_id"],
            WorkflowTransition.action_key == "verification_passed",
        ).scalar()
        assert verified_state_id is not None
        db.query(Bug).filter(Bug.id == verified_bug["id"]).update(
            {
                "current_state_id": verified_state_id,
                "creator_id": developer_id,
                "create_time": datetime.now() - timedelta(hours=30),
            }
        )
        db.query(Bug).filter(Bug.id == mentioned_bug["id"]).update({"creator_id": developer_id})
        db.query(Bug).filter(Bug.id == overdue_bug["id"]).update(
            {"creator_id": developer_id, "create_time": datetime.now() - timedelta(hours=30)}
        )
        db.add(
            ObjectWatch(
                object_type="task",
                object_id=watched_task["id"],
                user_id=developer_id,
                source="manual",
                enabled=True,
            )
        )
        db.add(
            ObjectWatch(
                object_type="requirement",
                object_id=created_requirement["id"],
                user_id=developer_id,
                source="manual",
                enabled=True,
            )
        )
        db.add(
            ObjectWatch(
                object_type="bug",
                object_id=mentioned_bug["id"],
                user_id=developer_id,
                source="manual",
                enabled=True,
            )
        )
        db.add(
            ObjectWatch(
                object_type="test_case",
                object_id=watched_test_case["id"],
                user_id=developer_id,
                source="manual",
                enabled=True,
            )
        )
        db.add(
            ObjectWatch(
                object_type="test_run",
                object_id=mentioned_test_run["id"],
                user_id=developer_id,
                source="manual",
                enabled=True,
            )
        )
        db.add(
            WorkItemComment(
                object_type="bug",
                object_id=mentioned_bug["id"],
                author_id=developer_id,
                body="@follow",
                mentioned_user_ids=[developer_id],
                mentions_metadata=[{"user_id": developer_id, "display_name": "Follow Developer"}],
            )
        )
        for object_type, object_id in (
            ("requirement", created_requirement["id"]),
            ("task", watched_task["id"]),
            ("test_case", watched_test_case["id"]),
        ):
            db.add(
                WorkItemComment(
                    object_type=object_type,
                    object_id=object_id,
                    author_id=developer_id,
                    body="@follow",
                    mentioned_user_ids=[developer_id],
                    mentions_metadata=[{"user_id": developer_id, "display_name": "Follow Developer"}],
                )
            )
        db.add(
            WorkItemComment(
                object_type="test_run",
                object_id=mentioned_test_run["id"],
                author_id=developer_id,
                body="@follow",
                mentioned_user_ids=[developer_id],
                mentions_metadata=[{"user_id": developer_id, "display_name": "Follow Developer"}],
            )
        )
        db.execute(
            __import__("sqlalchemy").text("update requirements set creator_id = :user_id where id = :id"),
            {"user_id": developer_id, "id": created_requirement["id"]},
        )
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/api/v1/dashboard/workbench",
        headers={"Authorization": f"Bearer {developer_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["created_by_me"]["label"] == "我发起的"
    assert created_requirement["id"] in {item["id"] for item in data["created_by_me"]["items"]}
    assert data["watched_by_me"]["label"] == "我关注的"
    watched_refs = {(item["object_type"], item["id"]) for item in data["watched_by_me"]["items"]}
    assert {
        ("requirement", created_requirement["id"]),
        ("task", watched_task["id"]),
        ("bug", mentioned_bug["id"]),
    } <= watched_refs
    assert {
        ("test_case", watched_test_case["id"]),
        ("test_run", mentioned_test_run["id"]),
    }.isdisjoint(watched_refs)
    assert data["mentioned_me"]["label"] == "提到我的"
    mentioned_refs = {(item["object_type"], item["id"]) for item in data["mentioned_me"]["items"]}
    assert {
        ("requirement", created_requirement["id"]),
        ("task", watched_task["id"]),
        ("bug", mentioned_bug["id"]),
    } <= mentioned_refs
    assert {
        ("test_case", watched_test_case["id"]),
        ("test_run", mentioned_test_run["id"]),
    }.isdisjoint(mentioned_refs)
    assert "project_board" not in data
    assert "iterations" not in data
    assert data["exception_center"]["label"] == "异常中心"
    exception_ids = {(item["object_type"], item["id"]) for item in data["exception_center"]["items"]}
    assert ("bug", verified_bug["id"]) in exception_ids
    assert ("bug", overdue_bug["id"]) in exception_ids
    exception_item = next(
        item for item in data["exception_center"]["items"]
        if item["object_type"] == "bug" and item["id"] == verified_bug["id"]
    )
    assert exception_item["entered_at"]
    assert exception_item["threshold_hours"] == 24
    assert exception_item["threshold_count"] is None
    assert exception_item["overdue_hours"] >= 0


def test_workbench_mentions_return_each_comment_with_its_content(client: TestClient):
    user_id, token = _create_user_with_role(f"mentioned_comment_{uuid4().hex[:6]}", "developer")
    project_id = _create_project(client, "Mention comment project")
    iteration_id = _create_iteration(client, project_id, "Mention comment iteration")
    _start_iteration(client, iteration_id)
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": "Comment context bug"},
    ).json()
    _add_project_member(project_id, user_id, "developer")

    db = SessionLocal()
    try:
        db.add_all([
            WorkItemComment(
                object_type="bug",
                object_id=bug["id"],
                author_id=user_id,
                body="@mentioned_comment 请先确认复现步骤",
                mentioned_user_ids=[user_id],
                create_time=datetime(2026, 7, 28, 10, 0, 0),
            ),
            WorkItemComment(
                object_type="bug",
                object_id=bug["id"],
                author_id=user_id,
                body="@mentioned_comment 已补充日志，请跟进",
                mentioned_user_ids=[user_id],
                create_time=datetime(2026, 7, 28, 11, 0, 0),
            ),
        ])
        db.commit()
    finally:
        db.close()

    response = client.get("/api/v1/dashboard/workbench", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    mentions = [item for item in response.json()["mentioned_me"]["items"] if item["id"] == bug["id"]]
    assert [item["mentioned_comment_body"] for item in mentions] == [
        "@mentioned_comment 已补充日志，请跟进",
        "@mentioned_comment 请先确认复现步骤",
    ]
    assert len({item["mentioned_comment_id"] for item in mentions}) == 2
    assert all(item["mentioned_comment_author_id"] == user_id for item in mentions)
    assert all(item["mentioned_comment_create_time"] for item in mentions)
    assert user_id in {user["id"] for user in response.json()["owners"]}


def test_authenticated_creates_immediately_appear_in_created_by_me(client: TestClient):
    user_id, token = _create_user_with_role(f"creator_user_{uuid4().hex[:6]}", "tester")
    project_id = _create_project(client, "Creator tracking project")
    iteration_id = _create_iteration(client, project_id, "Creator tracking iteration")
    _start_iteration(client, iteration_id)
    _add_project_member(project_id, user_id, "tester")
    headers = {"Authorization": f"Bearer {token}"}

    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": f"Created requirement {uuid4().hex[:8]}"},
        headers=headers,
    )
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": f"Created task {uuid4().hex[:8]}"},
        headers=headers,
    )
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": f"Created bug {uuid4().hex[:8]}"},
        headers=headers,
    )
    test_run = client.post(
        "/api/v1/test-runs",
        json={"project_id": project_id, "iteration_id": iteration_id, "name": f"Created test run {uuid4().hex[:8]}"},
        headers=headers,
    )

    for response in (requirement, task, bug, test_run):
        assert response.status_code in {200, 201}
        assert response.json()["creator_id"] == user_id

    workbench = client.get("/api/v1/dashboard/workbench", headers=headers).json()
    created_refs = {(item["object_type"], item["id"]) for item in workbench["created_by_me"]["items"]}
    assert {
        ("requirement", requirement.json()["id"]),
        ("task", task.json()["id"]),
        ("bug", bug.json()["id"]),
    } <= created_refs
    assert ("test_run", test_run.json()["id"]) not in created_refs


def test_workbench_scopes_execution_to_active_iterations_and_excludes_uniterated_items(client: TestClient):
    user_id, token = _create_user_with_role(f"active_scope_{uuid4().hex[:6]}", "product_manager")
    project_id = _create_project(client, "Active scope project")
    _add_project_member(project_id, user_id, "product_manager")
    planning_iteration_id = _create_iteration(client, project_id, "Planning iteration")
    active_iteration_id = _create_iteration(client, project_id, "Active iteration")
    _start_iteration(client, active_iteration_id)
    headers = {"Authorization": f"Bearer {token}"}

    active_requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project_id,
            "iteration_id": active_iteration_id,
            "title": "Active assigned requirement",
            "owner_id": user_id,
        },
        headers=headers,
    ).json()
    active_unassigned_task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "iteration_id": active_iteration_id,
            "title": "Active unassigned task",
        },
        headers=headers,
    ).json()
    planning_task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "iteration_id": planning_iteration_id,
            "title": "Planning assigned task",
            "owner_id": user_id,
        },
        headers=headers,
    ).json()
    uniterated_requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project_id,
            "title": "Uniterated requirement",
            "owner_id": user_id,
        },
        headers=headers,
    ).json()
    uniterated_task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "title": "Uniterated task"},
        headers=headers,
    ).json()
    uniterated_bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "title": "Uniterated bug", "owner_id": user_id},
        headers=headers,
    ).json()

    db = SessionLocal()
    try:
        db.add(
            ObjectWatch(
                object_type="task",
                object_id=uniterated_task["id"],
                user_id=user_id,
                source="manual",
                enabled=True,
            )
        )
        db.add(
            WorkItemComment(
                object_type="bug",
                object_id=uniterated_bug["id"],
                author_id=user_id,
                body="@active_scope",
                mentioned_user_ids=[user_id],
                mentions_metadata=[{"user_id": user_id, "display_name": "Active scope user"}],
            )
        )
        db.commit()
    finally:
        db.close()

    data = client.get("/api/v1/dashboard/workbench", headers=headers).json()
    pending_refs = {(item["object_type"], item["id"]) for item in data["pending_handling"]["items"]}
    unassigned_refs = {(item["object_type"], item["id"]) for item in data["unassigned"]["items"]}
    created_refs = {(item["object_type"], item["id"]) for item in data["created_by_me"]["items"]}

    assert "unplanned" not in data
    assert pending_refs == {("requirement", active_requirement["id"])}
    assert unassigned_refs == {("task", active_unassigned_task["id"])}
    assert ("requirement", active_requirement["id"]) in created_refs
    assert ("task", planning_task["id"]) not in created_refs
    uniterated_refs = {
        ("requirement", uniterated_requirement["id"]),
        ("task", uniterated_task["id"]),
        ("bug", uniterated_bug["id"]),
    }
    for section in (
        "pending_handling",
        "unassigned",
        "created_by_me",
        "watched_by_me",
        "mentioned_me",
        "exception_center",
    ):
        section_refs = {(item["object_type"], item["id"]) for item in data[section]["items"]}
        assert uniterated_refs.isdisjoint(section_refs)


def test_workbench_empty_project_scope_is_not_all_projects(client: TestClient):
    _, outsider_token = _create_user_with_role(f"scope_outsider_{uuid4().hex[:6]}", "developer")
    project_id = _create_project(client, "Invisible workbench project")
    iteration_id = _create_iteration(client, project_id, "Invisible active iteration")
    _start_iteration(client, iteration_id)
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": "Invisible unassigned task"},
    ).json()

    data = client.get(
        "/api/v1/dashboard/workbench",
        headers={"Authorization": f"Bearer {outsider_token}"},
    ).json()
    visible_refs = {
        (item["object_type"], item["id"])
        for section in ("pending_handling", "unassigned", "exception_center")
        for item in data[section]["items"]
    }

    assert ("task", task["id"]) not in visible_refs


def test_terminal_iteration_integrity_scan_short_circuits_empty_project_scope():
    db = Mock()
    db.query.side_effect = AssertionError("empty project scope must not query historical work items")

    assert _terminal_iteration_open_item_refs(db, set()) == []
    db.query.assert_not_called()


def test_system_admin_workbench_has_explicit_all_project_scope(client: TestClient):
    _, admin_token = _create_user_with_role(f"scope_admin_{uuid4().hex[:6]}", "system_admin")
    project_id = _create_project(client, "Admin workbench project")
    iteration_id = _create_iteration(client, project_id, "Admin active iteration")
    _start_iteration(client, iteration_id)
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": "Admin visible unassigned task"},
    ).json()

    data = client.get(
        "/api/v1/dashboard/workbench",
        headers={"Authorization": f"Bearer {admin_token}"},
    ).json()

    assert ("task", task["id"]) in {
        (item["object_type"], item["id"]) for item in data["unassigned"]["items"]
    }


def test_terminal_iteration_open_item_is_only_reported_as_integrity_exception(client: TestClient):
    user_id, token = _create_user_with_role(f"integrity_user_{uuid4().hex[:6]}", "developer")
    project_id = _create_project(client, "Integrity exception project")
    _add_project_member(project_id, user_id, "developer")
    iteration_id = _create_iteration(client, project_id, "Completed integrity iteration")
    _start_iteration(client, iteration_id)
    completed = client.post(
        f"/api/v1/workflow-runtime/iteration/{iteration_id}/transition",
        json={"action_key": "complete"},
    )
    assert completed.status_code == 200
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "title": "Legacy open task", "owner_id": user_id},
    ).json()
    db = SessionLocal()
    try:
        db.query(Task).filter(Task.id == task["id"]).update({"iteration_id": iteration_id})
        db.commit()
    finally:
        db.close()

    data = client.get(
        "/api/v1/dashboard/workbench",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    pending_refs = {(item["object_type"], item["id"]) for item in data["pending_handling"]["items"]}
    exception_item = next(
        item
        for item in data["exception_center"]["items"]
        if item["object_type"] == "task" and item["id"] == task["id"]
    )

    assert ("task", task["id"]) not in pending_refs
    assert exception_item["exception_key"] == "terminal_iteration_open_item"


def test_workbench_move_endpoint_is_removed(client: TestClient):
    response = client.post(
        "/api/v1/dashboard/workbench/move",
        json={"object_type": "task", "object_id": 1, "target_iteration_id": 1},
    )

    assert response.status_code == 404


def test_workbench_requires_authentication(client: TestClient):
    response = client.get(
        "/api/v1/dashboard/workbench",
        headers={"X-Test-No-Auth": "1"},
    )

    assert response.status_code == 401


def test_workbench_uses_requirement_iteration_for_legacy_linked_task(client: TestClient):
    user_id, token = _create_user_with_role(f"linked_task_scope_{uuid4().hex[:6]}", "developer")
    project_id = _create_project(client, "Linked task inherited iteration")
    iteration_id = _create_iteration(client, project_id, "Linked task active iteration")
    _start_iteration(client, iteration_id)
    _add_project_member(project_id, user_id, "developer")
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": "Iteration requirement", "owner_id": user_id},
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "requirement_id": requirement["id"], "title": "Legacy linked task", "owner_id": user_id},
    ).json()

    db = SessionLocal()
    try:
        db.query(Task).filter(Task.id == task["id"]).update({"iteration_id": None})
        db.commit()
    finally:
        db.close()

    workbench = client.get("/api/v1/dashboard/workbench", headers={"Authorization": f"Bearer {token}"}).json()
    pending_refs = {(item["object_type"], item["id"]) for item in workbench["pending_handling"]["items"]}
    active_items = {(item["object_type"], item["id"]): item for item in workbench["active_iteration_items"]}

    assert ("task", task["id"]) in pending_refs
    assert active_items[("task", task["id"])]["iteration_id"] == iteration_id


def test_workbench_excludes_requirement_pool_items_even_when_pool_state_looks_active(client: TestClient):
    user_id, token = _create_user_with_role(f"pool_scope_{uuid4().hex[:6]}", "developer")
    project_response = client.post("/api/v1/projects", json={"name": "Pool workbench scope"})
    assert project_response.status_code == 200
    project = project_response.json()
    delivery_id = _create_iteration(client, project["id"], "State source")
    _start_iteration(client, delivery_id)
    _add_project_member(project["id"], user_id, "developer")
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "title": "Unscheduled requirement", "owner_id": user_id},
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "requirement_id": requirement["id"], "title": "Inherited pool task", "owner_id": user_id},
    ).json()

    db = SessionLocal()
    try:
        active_state_id = db.query(Iteration.current_state_id).filter(Iteration.id == delivery_id).scalar()
        db.query(Iteration).filter(Iteration.id == project["requirement_pool_iteration_id"]).update(
            {"current_state_id": active_state_id}
        )
        db.commit()
    finally:
        db.close()

    workbench = client.get("/api/v1/dashboard/workbench", headers={"Authorization": f"Bearer {token}"}).json()
    visible_refs = {
        (item["object_type"], item["id"])
        for section in ("pending_handling", "unassigned", "created_by_me", "watched_by_me", "mentioned_me")
        for item in workbench[section]["items"]
    }

    assert ("requirement", requirement["id"]) not in visible_refs
    assert ("task", task["id"]) not in visible_refs
