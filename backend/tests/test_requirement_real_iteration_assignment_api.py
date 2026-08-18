from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.session import SessionLocal
from app.models.iteration import Iteration, IterationProject
from app.models.project import Project
from app.models.user import User
from app.models.workflow_definition import WorkflowState
from app.models.work_item_iteration_history import WorkItemIterationHistory


def _create_project(client: TestClient, prefix: str = "Real iteration") -> dict:
    response = client.post("/api/v1/projects", json={"name": f"{prefix}-{uuid4().hex[:8]}"})
    assert response.status_code == 200, response.text
    return response.json()


def _create_iteration(client: TestClient, project_id: int, prefix: str = "Iteration") -> dict:
    response = client.post(
        "/api/v1/iterations",
        json={"name": f"{prefix}-{uuid4().hex[:8]}", "project_ids": [project_id]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _start_iteration(client: TestClient, iteration_id: int) -> dict:
    response = client.post(
        f"/api/v1/workflow-runtime/iteration/{iteration_id}/transition",
        json={
            "action_key": "start",
            "payload": {"effective_time": "2026-08-11T09:00:00"},
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["state_category"] == "normal"
    return response.json()


def _set_iteration_category(iteration_id: int, category: str) -> None:
    db = SessionLocal()
    try:
        iteration = db.query(Iteration).filter(Iteration.id == iteration_id).one()
        state = (
            db.query(WorkflowState)
            .filter(
                WorkflowState.definition_id == iteration.workflow_definition_id,
                WorkflowState.category == category,
            )
            .order_by(WorkflowState.sort_order.asc(), WorkflowState.id.asc())
            .first()
        )
        assert state is not None
        iteration.current_state_id = state.id
        db.commit()
    finally:
        db.close()


def _create_project_owner(project_id: int) -> tuple[int, str]:
    db = SessionLocal()
    try:
        user = User(
            username=f"iteration_owner_{uuid4().hex[:8]}",
            full_name="Iteration owner",
            password_hash=get_password_hash("User123456"),
            is_active=True,
        )
        db.add(user)
        db.flush()
        db.query(Project).filter(Project.id == project_id).update({"owner_id": user.id})
        db.commit()
        return user.id, create_access_token(user.username)
    finally:
        db.close()


def test_project_creation_does_not_provision_a_default_iteration(client: TestClient):
    project = _create_project(client, "No default iteration")

    assert "requirement_pool_iteration_id" not in project
    db = SessionLocal()
    try:
        memberships = db.query(IterationProject).filter(
            IterationProject.project_id == project["id"]
        ).all()
        assert memberships == []
    finally:
        db.close()


@pytest.mark.parametrize("iteration_payload", [{}, {"iteration_id": None}])
def test_requirement_create_requires_explicit_iteration(client: TestClient, iteration_payload: dict):
    project = _create_project(client)
    response = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "title": "Iteration is required", **iteration_payload},
    )
    assert response.status_code == 422


def test_requirement_create_accepts_only_eligible_project_scoped_iteration(client: TestClient):
    project = _create_project(client, "Target")
    other_project = _create_project(client, "Other")
    eligible = _create_iteration(client, project["id"], "Eligible")
    closed = _create_iteration(client, project["id"], "Closed")
    foreign = _create_iteration(client, other_project["id"], "Foreign")
    _start_iteration(client, eligible["id"])
    _set_iteration_category(closed["id"], "terminal")
    accepted = client.post("/api/v1/requirements", json={"project_id": project["id"], "iteration_id": eligible["id"], "title": "Accepted"})
    closed_response = client.post("/api/v1/requirements", json={"project_id": project["id"], "iteration_id": closed["id"], "title": "Closed"})
    foreign_response = client.post("/api/v1/requirements", json={"project_id": project["id"], "iteration_id": foreign["id"], "title": "Foreign"})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["iteration_id"] == eligible["id"]
    assert closed_response.status_code == 400
    assert foreign_response.status_code == 400


def test_requirement_update_accepts_started_iteration(client: TestClient):
    project = _create_project(client, "Update to started")
    source = _create_iteration(client, project["id"], "Source")
    active = _create_iteration(client, project["id"], "Active")
    _start_iteration(client, active["id"])
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "iteration_id": source["id"], "title": "Move me"},
    ).json()

    moved = client.patch(
        f"/api/v1/requirements/{requirement['id']}", json={"iteration_id": active["id"]}
    )

    assert moved.status_code == 200, moved.text
    assert moved.json()["iteration_id"] == active["id"]


def test_work_item_fallback_prefers_started_iteration(client: TestClient):
    project = _create_project(client, "Started fallback")
    active = _create_iteration(client, project["id"], "Active")
    _start_iteration(client, active["id"])

    task = client.post("/api/v1/tasks", json={"project_id": project["id"], "title": "Task"})

    assert task.status_code == 200, task.text
    assert task.json()["iteration_id"] == active["id"]


def test_requirement_update_rejects_clearing_or_closed_iteration(client: TestClient):
    project = _create_project(client)
    eligible = _create_iteration(client, project["id"], "Eligible")
    closed = _create_iteration(client, project["id"], "Closed")
    requirement = client.post("/api/v1/requirements", json={"project_id": project["id"], "iteration_id": eligible["id"], "title": "Existing"}).json()
    _set_iteration_category(closed["id"], "terminal")
    cleared = client.patch(f"/api/v1/requirements/{requirement['id']}", json={"iteration_id": None})
    moved_to_closed = client.patch(f"/api/v1/requirements/{requirement['id']}", json={"iteration_id": closed["id"]})
    assert cleared.status_code == 422
    assert moved_to_closed.status_code == 400


def test_task_and_bug_fallback_share_auto_created_real_unstarted_iteration(client: TestClient):
    project = _create_project(client, "Fallback")
    task = client.post("/api/v1/tasks", json={"project_id": project["id"], "title": "Task"})
    bug = client.post("/api/v1/bugs", json={"project_id": project["id"], "title": "Bug"})
    assert task.status_code == 200, task.text
    assert bug.status_code == 200, bug.text
    assert task.json()["iteration_id"] == bug.json()["iteration_id"]
    db = SessionLocal()
    try:
        target = db.query(Iteration).filter(Iteration.id == task.json()["iteration_id"]).one()
        assert target.state_category == "start"
        assert db.query(IterationProject).filter(IterationProject.project_id == project["id"]).count() == 1
    finally:
        db.close()


def test_inherited_invalid_iteration_falls_back_but_explicit_terminal_is_rejected(client: TestClient):
    project = _create_project(client, "Inherited fallback")
    other_project = _create_project(client, "Inherited foreign")
    fallback_id = _create_iteration(client, project["id"], "Fallback")["id"]
    terminal = _create_iteration(client, project["id"], "Terminal source")
    deleted = _create_iteration(client, project["id"], "Deleted source")
    foreign = _create_iteration(client, other_project["id"], "Foreign source")
    _set_iteration_category(terminal["id"], "terminal")
    db = SessionLocal()
    try:
        db.query(Iteration).filter(Iteration.id == deleted["id"]).update({"deleted": 1})
        db.commit()
    finally:
        db.close()

    explicit = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "iteration_id": terminal["id"], "title": "Explicit"},
    )
    assert explicit.status_code == 409

    from app.services.iteration_assignment_service import resolve_work_item_iteration

    db = SessionLocal()
    try:
        for source_id in (terminal["id"], deleted["id"], foreign["id"]):
            assert resolve_work_item_iteration(
                db, project["id"], None, source_iteration_id=source_id
            ) == fallback_id
    finally:
        db.close()


def test_test_case_bug_rejects_terminal_source_iteration(client: TestClient):
    project = _create_project(client, "Test case source fallback")
    source = _create_iteration(client, project["id"], "Historical case iteration")
    test_case = client.post(
        "/api/v1/test-cases",
        json={"project_id": project["id"], "iteration_id": source["id"], "title": "Failed case"},
    ).json()
    executed = client.post(
        f"/api/v1/test-cases/{test_case['id']}/executions",
        json={"steps_result_json": [{"step": "submit", "result": "failed"}]},
    )
    assert executed.status_code == 200, executed.text
    _set_iteration_category(source["id"], "terminal")

    bug = client.post(
        f"/api/v1/test-cases/{test_case['id']}/bugs", json={"title": "Case failure"}
    )

    assert bug.status_code == 409, bug.text
    assert bug.json()["detail"]["code"] == "ITERATION_NOT_MUTABLE"


def test_test_run_bug_rejects_terminal_source_iteration(client: TestClient):
    project = _create_project(client, "Test run source fallback")
    source = _create_iteration(client, project["id"], "Historical run iteration")
    test_case = client.post(
        "/api/v1/test-cases", json={"project_id": project["id"], "title": "Run case"}
    ).json()
    test_run = client.post(
        "/api/v1/test-runs",
        json={"project_id": project["id"], "iteration_id": source["id"], "name": "Historical run"},
    ).json()
    run_case = client.post(
        f"/api/v1/test-runs/{test_run['id']}/cases",
        json={"test_case_ids": [test_case["id"]]},
    ).json()[0]
    failed = client.patch(f"/api/v1/test-run-cases/{run_case['id']}", json={"result": "failed"})
    assert failed.status_code == 200, failed.text
    _set_iteration_category(source["id"], "terminal")

    bug = client.post(
        f"/api/v1/test-run-cases/{run_case['id']}/bugs", json={"title": "Run failure"}
    )

    assert bug.status_code == 409, bug.text
    assert bug.json()["detail"]["code"] == "ITERATION_NOT_MUTABLE"


def test_iteration_delete_rehomes_work_items_and_preserves_iteration_history(client: TestClient):
    project = _create_project(client, "Delete source")
    source = _create_iteration(client, project["id"], "Source")
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "iteration_id": source["id"], "title": "Requirement"},
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "iteration_id": source["id"], "title": "Task"},
    ).json()
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project["id"], "iteration_id": source["id"], "title": "Bug"},
    ).json()

    deleted = client.delete(f"/api/v1/iterations/{source['id']}")

    assert deleted.status_code == 204, deleted.text
    moved_ids = {
        client.get(f"/api/v1/requirements/{requirement['id']}").json()["iteration_id"],
        client.get(f"/api/v1/tasks/{task['id']}").json()["iteration_id"],
        client.get(f"/api/v1/bugs/{bug['id']}").json()["iteration_id"],
    }
    assert len(moved_ids) == 1
    target_id = moved_ids.pop()
    assert target_id != source["id"]

    db = SessionLocal()
    try:
        target = db.query(Iteration).filter(Iteration.id == target_id).one()
        assert target.state_category == "start"
        for object_type, object_id in (
            ("requirement", requirement["id"]),
            ("task", task["id"]),
            ("bug", bug["id"]),
        ):
            rows = db.query(WorkItemIterationHistory).filter(
                WorkItemIterationHistory.object_type == object_type,
                WorkItemIterationHistory.object_id == object_id,
            ).order_by(WorkItemIterationHistory.id.asc()).all()
            assert rows[-2].iteration_id == source["id"]
            assert rows[-2].left_at is not None
            assert rows[-1].iteration_id == target_id
            assert rows[-1].left_at is None
    finally:
        db.close()


def test_requirement_project_change_requires_explicit_target_project_iteration(client: TestClient):
    source_project = _create_project(client, "Move source")
    target_project = _create_project(client, "Move target")
    source_iteration = _create_iteration(client, source_project["id"], "Source")
    target_iteration = _create_iteration(client, target_project["id"], "Target")
    requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": source_project["id"],
            "iteration_id": source_iteration["id"],
            "title": "Move requirement",
        },
    ).json()

    missing_target = client.patch(
        f"/api/v1/requirements/{requirement['id']}", json={"project_id": target_project["id"]}
    )
    moved = client.patch(
        f"/api/v1/requirements/{requirement['id']}",
        json={"project_id": target_project["id"], "iteration_id": target_iteration["id"]},
    )

    assert missing_target.status_code == 422
    assert moved.status_code == 200, moved.text
    assert moved.json()["project_id"] == target_project["id"]
    assert moved.json()["iteration_id"] == target_iteration["id"]


def test_requirement_project_change_requires_permission_on_target_project(client: TestClient):
    source_project = _create_project(client, "Authorized source")
    target_project = _create_project(client, "Unauthorized target")
    source_iteration = _create_iteration(client, source_project["id"], "Source")
    target_iteration = _create_iteration(client, target_project["id"], "Target")
    _user_id, token = _create_project_owner(source_project["id"])
    requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": source_project["id"],
            "iteration_id": source_iteration["id"],
            "title": "Protected move",
        },
    ).json()

    denied = client.patch(
        f"/api/v1/requirements/{requirement['id']}",
        json={"project_id": target_project["id"], "iteration_id": target_iteration["id"]},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert denied.status_code == 403, denied.text
    unchanged = client.get(f"/api/v1/requirements/{requirement['id']}").json()
    assert unchanged["project_id"] == source_project["id"]
    assert unchanged["iteration_id"] == source_iteration["id"]


def test_changing_task_or_bug_source_inherits_source_iteration_without_iteration_patch(client: TestClient):
    project = _create_project(client, "Association inheritance")
    source = _create_iteration(client, project["id"], "Old iteration")
    target = _create_iteration(client, project["id"], "Source iteration")
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "iteration_id": target["id"], "title": "Source requirement"},
    ).json()
    source_task = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "iteration_id": target["id"], "title": "Source task"},
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "iteration_id": source["id"], "title": "Task to link"},
    ).json()
    bug_for_task = client.post(
        "/api/v1/bugs",
        json={"project_id": project["id"], "iteration_id": source["id"], "title": "Bug to task"},
    ).json()
    bug_for_requirement = client.post(
        "/api/v1/bugs",
        json={"project_id": project["id"], "iteration_id": source["id"], "title": "Bug to requirement"},
    ).json()

    updated_task = client.patch(
        f"/api/v1/tasks/{task['id']}", json={"requirement_id": requirement["id"]}
    )
    updated_bug_task = client.patch(
        f"/api/v1/bugs/{bug_for_task['id']}", json={"task_id": source_task["id"]}
    )
    updated_bug_requirement = client.patch(
        f"/api/v1/bugs/{bug_for_requirement['id']}", json={"requirement_id": requirement["id"]}
    )

    assert updated_task.status_code == 200, updated_task.text
    assert updated_task.json()["iteration_id"] == target["id"]
    assert updated_bug_task.status_code == 200, updated_bug_task.text
    assert updated_bug_task.json()["iteration_id"] == target["id"]
    assert updated_bug_requirement.status_code == 200, updated_bug_requirement.text
    assert updated_bug_requirement.json()["iteration_id"] == target["id"]


def test_requirement_iteration_change_atomically_moves_linked_tasks_and_following_bugs(client: TestClient):
    project = _create_project(client, "Requirement cascade")
    source = _create_iteration(client, project["id"], "Source iteration")
    target = _create_iteration(client, project["id"], "Target iteration")
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "iteration_id": source["id"], "title": "Cascade requirement"},
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "requirement_id": requirement["id"], "title": "Linked task"},
    ).json()
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project["id"], "requirement_id": requirement["id"], "title": "Following bug"},
    ).json()

    moved = client.patch(
        f"/api/v1/requirements/{requirement['id']}", json={"iteration_id": target["id"]}
    )

    assert moved.status_code == 200, moved.text
    assert client.get(f"/api/v1/tasks/{task['id']}").json()["iteration_id"] == target["id"]
    assert client.get(f"/api/v1/bugs/{bug['id']}").json()["iteration_id"] == target["id"]
    db = SessionLocal()
    try:
        for object_type, object_id in (("requirement", requirement["id"]), ("task", task["id"]), ("bug", bug["id"])):
            rows = (
                db.query(WorkItemIterationHistory)
                .filter(
                    WorkItemIterationHistory.object_type == object_type,
                    WorkItemIterationHistory.object_id == object_id,
                )
                .order_by(WorkItemIterationHistory.id.asc())
                .all()
            )
            assert rows[-2].iteration_id == source["id"]
            assert rows[-2].left_at is not None
            assert rows[-1].iteration_id == target["id"]
            assert rows[-1].left_at is None
    finally:
        db.close()


def test_requirement_iteration_change_rejects_linked_task_in_terminal_source_iteration(client: TestClient):
    project = _create_project(client, "Terminal dependent task")
    requirement_source = _create_iteration(client, project["id"], "Requirement source")
    task_source = _create_iteration(client, project["id"], "Task terminal source")
    target = _create_iteration(client, project["id"], "Requirement target")
    requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project["id"],
            "iteration_id": requirement_source["id"],
            "title": "Requirement with divergent task",
        },
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project["id"],
            "requirement_id": requirement["id"],
            "iteration_id": task_source["id"],
            "title": "Divergent linked task",
        },
    ).json()
    assert task["iteration_id"] == requirement_source["id"]
    moved_task = client.patch(
        f"/api/v1/tasks/{task['id']}", json={"iteration_id": task_source["id"]}
    )
    assert moved_task.status_code == 200, moved_task.text
    _set_iteration_category(task_source["id"], "terminal")

    rejected = client.patch(
        f"/api/v1/requirements/{requirement['id']}", json={"iteration_id": target["id"]}
    )

    assert rejected.status_code == 409, rejected.text
    assert client.get(f"/api/v1/requirements/{requirement['id']}").json()["iteration_id"] == requirement_source["id"]
    assert client.get(f"/api/v1/tasks/{task['id']}").json()["iteration_id"] == task_source["id"]
    db = SessionLocal()
    try:
        open_task_history = db.query(WorkItemIterationHistory).filter(
            WorkItemIterationHistory.object_type == "task",
            WorkItemIterationHistory.object_id == task["id"],
            WorkItemIterationHistory.left_at.is_(None),
        ).one()
        assert open_task_history.iteration_id == task_source["id"]
    finally:
        db.close()


def test_project_planning_pool_aggregates_all_items_in_eligible_iterations(client: TestClient):
    project = _create_project(client, "Planning aggregate")
    unstarted = _create_iteration(client, project["id"], "Unstarted")
    active = _create_iteration(client, project["id"], "Active")
    _start_iteration(client, active["id"])

    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "iteration_id": unstarted["id"], "title": "Requirement"},
    ).json()
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "iteration_id": active["id"], "title": "Task"},
    ).json()
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project["id"], "iteration_id": active["id"], "title": "Bug"},
    ).json()

    page = client.get(f"/api/v1/projects/{project['id']}/iterations").json()
    planning = page["planning_pool"]
    assert set(planning["iteration_ids"]) == {unstarted["id"], active["id"]}
    assert planning["requirement_count"] == 1
    assert planning["task_count"] == 1
    assert planning["bug_count"] == 1
    assert planning["total_count"] == 3

    requirement_page = client.get(
        f"/api/v1/projects/{project['id']}/requirements", params={"planning_pool": True}
    ).json()
    task_page = client.get(
        f"/api/v1/projects/{project['id']}/tasks", params={"planning_pool": True}
    ).json()
    bug_page = client.get(
        f"/api/v1/projects/{project['id']}/bugs", params={"planning_pool": True}
    ).json()
    assert [item["id"] for item in requirement_page["items"]] == [requirement["id"]]
    assert [item["id"] for item in task_page["items"]] == [task["id"]]
    assert [item["id"] for item in bug_page["items"]] == [bug["id"]]


def test_child_project_reuses_parent_iteration_for_fallback_and_planning_pool(client: TestClient):
    parent = _create_project(client, "Parent scope")
    child_response = client.post(
        "/api/v1/projects",
        json={"name": f"Child scope-{uuid4().hex[:8]}", "parent_id": parent["id"]},
    )
    assert child_response.status_code == 200, child_response.text
    child = child_response.json()
    parent_iteration = _create_iteration(client, parent["id"], "Parent delivery")
    _start_iteration(client, parent_iteration["id"])

    requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": child["id"],
            "iteration_id": parent_iteration["id"],
            "title": "Child requirement",
        },
    )
    task = client.post("/api/v1/tasks", json={"project_id": child["id"], "title": "Child task"})
    bug = client.post(
        "/api/v1/bugs",
        json={
            "project_id": child["id"],
            "iteration_id": parent_iteration["id"],
            "title": "Child bug",
        },
    )

    assert requirement.status_code == 200, requirement.text
    assert task.status_code == 200, task.text
    assert task.json()["iteration_id"] == parent_iteration["id"]
    assert bug.status_code == 200, bug.text

    planning = client.get(f"/api/v1/projects/{child['id']}/iterations").json()["planning_pool"]
    assert parent_iteration["id"] in planning["iteration_ids"]
    assert planning["requirement_count"] == 1
    assert planning["task_count"] == 1
    assert planning["bug_count"] == 1
    assert planning["total_count"] == 3


def test_iteration_available_and_link_endpoints_move_items_from_other_eligible_iterations(client: TestClient):
    project = _create_project(client, "Iteration linking")
    source = _create_iteration(client, project["id"], "Link source")
    target = _create_iteration(client, project["id"], "Link target")
    terminal_source = _create_iteration(client, project["id"], "Closed link source")
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "iteration_id": source["id"], "title": "Available requirement"},
    ).json()
    linked_task = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "requirement_id": requirement["id"], "title": "Requirement task"},
    ).json()
    standalone_task = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "iteration_id": source["id"], "title": "Available task"},
    ).json()
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project["id"], "iteration_id": source["id"], "title": "Movable bug"},
    ).json()
    closed_requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project["id"],
            "iteration_id": terminal_source["id"],
            "title": "Closed source requirement",
        },
    ).json()
    _set_iteration_category(terminal_source["id"], "terminal")

    available_requirements = client.get(
        f"/api/v1/iterations/{target['id']}/available-requirements"
    )
    available_tasks = client.get(f"/api/v1/iterations/{target['id']}/available-tasks")

    assert available_requirements.status_code == 200, available_requirements.text
    assert requirement["id"] in {item["id"] for item in available_requirements.json()}
    assert closed_requirement["id"] not in {item["id"] for item in available_requirements.json()}
    assert available_tasks.status_code == 200, available_tasks.text
    assert standalone_task["id"] in {item["id"] for item in available_tasks.json()}
    assert linked_task["id"] not in {item["id"] for item in available_tasks.json()}

    moved_requirements = client.post(
        f"/api/v1/iterations/{target['id']}/requirements",
        json={"requirement_ids": [requirement["id"]]},
    )
    moved_tasks = client.post(
        f"/api/v1/iterations/{target['id']}/tasks", json={"task_ids": [standalone_task["id"]]}
    )
    moved_bugs = client.post(
        f"/api/v1/iterations/{target['id']}/bugs", json={"bug_ids": [bug["id"]]}
    )
    rejected_closed_source = client.post(
        f"/api/v1/iterations/{target['id']}/requirements",
        json={"requirement_ids": [closed_requirement["id"]]},
    )

    assert moved_requirements.status_code == 200, moved_requirements.text
    assert moved_tasks.status_code == 200, moved_tasks.text
    assert moved_bugs.status_code == 200, moved_bugs.text
    assert rejected_closed_source.status_code == 409, rejected_closed_source.text
    assert client.get(f"/api/v1/tasks/{linked_task['id']}").json()["iteration_id"] == target["id"]
    for object_type, object_id, endpoint in (
        ("requirement", requirement["id"], "requirements"),
        ("task", linked_task["id"], "tasks"),
        ("task", standalone_task["id"], "tasks"),
        ("bug", bug["id"], "bugs"),
    ):
        assert client.get(f"/api/v1/{endpoint}/{object_id}").json()["iteration_id"] == target["id"]
        db = SessionLocal()
        try:
            histories = (
                db.query(WorkItemIterationHistory)
                .filter(
                    WorkItemIterationHistory.object_type == object_type,
                    WorkItemIterationHistory.object_id == object_id,
                )
                .order_by(WorkItemIterationHistory.id.asc())
                .all()
            )
            assert histories[-2].left_at is not None
            assert histories[-1].iteration_id == target["id"]
            assert histories[-1].left_at is None
        finally:
            db.close()


def test_iteration_available_and_link_endpoints_reject_terminal_target(client: TestClient):
    project = _create_project(client, "Closed link target")
    source = _create_iteration(client, project["id"], "Mutable source")
    target = _create_iteration(client, project["id"], "Closed target")
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "iteration_id": source["id"], "title": "Must stay"},
    ).json()
    _set_iteration_category(target["id"], "terminal")

    available = client.get(f"/api/v1/iterations/{target['id']}/available-requirements")
    linked = client.post(
        f"/api/v1/iterations/{target['id']}/requirements",
        json={"requirement_ids": [requirement["id"]]},
    )

    assert available.status_code == 409, available.text
    assert linked.status_code == 409, linked.text
    assert client.get(f"/api/v1/requirements/{requirement['id']}").json()["iteration_id"] == source["id"]
