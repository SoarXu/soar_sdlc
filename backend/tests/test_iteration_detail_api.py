from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.jobs.iteration_jobs import run_auto_start_due_iterations
from app.models.requirement import Requirement
from app.models.bug import Bug
from app.models.iteration import Iteration
from app.models.task import Task
from app.models.work_item_iteration_history import WorkItemIterationHistory
from app.models.workflow_definition import WorkflowState, WorkflowTransition
from app.services import iteration_service


def test_iteration_loader_can_request_a_database_row_lock():
    class QuerySpy:
        def __init__(self):
            self.locked = False
            self.item = object()

        def filter(self, *args):
            return self

        def with_for_update(self):
            self.locked = True
            return self

        def first(self):
            return self.item

    class SessionSpy:
        def __init__(self):
            self.query_spy = QuerySpy()

        def query(self, model):
            return self.query_spy

    db = SessionSpy()

    item = iteration_service._get_active_iteration(db, 1, for_update=True)

    assert item is db.query_spy.item
    assert db.query_spy.locked is True


def test_iteration_creation_uses_system_workflow_initial_state(client: TestClient):
    project_id = _create_project(client)
    created = client.post(
        "/api/v1/iterations",
        json={"project_ids": [project_id], "name": f"ID Iteration-{uuid4().hex[:8]}"},
    )

    assert created.status_code == 200
    data = created.json()
    assert isinstance(data["workflow_definition_id"], int)
    assert isinstance(data["current_state_id"], int)
    assert data["status_name"]

    db = SessionLocal()
    try:
        state = db.query(WorkflowState).filter(WorkflowState.id == data["current_state_id"]).one()
        assert state.definition_id == data["workflow_definition_id"]
        assert state.category == "start"
        assert data["status_name"] == state.status_name
    finally:
        db.close()


def _create_project(client: TestClient, name: str | None = None, parent_id: int | None = None) -> int:
    payload = {"name": name or f"Project-{uuid4().hex[:8]}"}
    if parent_id:
        payload["parent_id"] = parent_id
    response = client.post("/api/v1/projects", json=payload)
    assert response.status_code == 200
    return response.json()["id"]


def _create_iteration(client: TestClient, project_ids: list[int], name: str | None = None, status: str = "planning") -> int:
    response = client.post(
        "/api/v1/iterations",
        json={"project_ids": project_ids, "name": name or f"Iteration-{uuid4().hex[:8]}"},
    )
    assert response.status_code == 200
    iteration_id = response.json()["id"]
    if status == "active":
        started = client.post(
            f"/api/v1/workflow-runtime/iteration/{iteration_id}/transition",
            json={"action_key": "start", "payload": {}},
        )
        assert started.status_code == 200, started.text
    return iteration_id


def _create_requirement(client: TestClient, project_id: int, title: str | None = None, owner_id: int | None = None) -> int:
    response = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": title or f"Requirement-{uuid4().hex[:8]}", "owner_id": owner_id},
    )
    assert response.status_code == 200
    return response.json()["id"]


def _create_task(
    client: TestClient,
    project_id: int,
    title: str | None = None,
    requirement_id: int | None = None,
    owner_id: int | None = None,
) -> int:
    payload = {"project_id": project_id, "title": title or f"Task-{uuid4().hex[:8]}", "owner_id": owner_id}
    if requirement_id:
        payload["requirement_id"] = requirement_id
    response = client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 200
    return response.json()["id"]


def _create_case(client: TestClient, project_id: int, requirement_id: int, title: str | None = None) -> int:
    response = client.post(
        "/api/v1/test-cases",
        json={"project_id": project_id, "requirement_id": requirement_id, "title": title or f"Case-{uuid4().hex[:8]}"},
    )
    assert response.status_code == 200
    return response.json()["id"]


def _create_bug(client: TestClient, project_id: int, iteration_id: int, title: str | None = None, owner_id: int | None = None) -> int:
    response = client.post(
        "/api/v1/bugs",
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
            "title": title or f"Bug-{uuid4().hex[:8]}",
            "owner_id": owner_id,
        },
    )
    assert response.status_code == 200
    return response.json()["id"]


def _mark_iteration_terminal(iteration_id: int) -> None:
    db = SessionLocal()
    try:
        iteration = db.query(Iteration).filter(Iteration.id == iteration_id).one()
        terminal_state = db.query(WorkflowState).filter(
            WorkflowState.definition_id == iteration.workflow_definition_id,
            WorkflowState.category == "terminal",
        ).first()
        assert terminal_state is not None
        iteration.current_state_id = terminal_state.id
        db.commit()
    finally:
        db.close()


def _set_requirement_status(requirement_id: int, status: str) -> None:
    db = SessionLocal()
    try:
        requirement = db.query(Requirement).filter(Requirement.id == requirement_id).first()
        requirement.current_state_id = _state_id_for_status(db, requirement, status)
        db.commit()
    finally:
        db.close()


def _set_task_status(task_id: int, status: str) -> None:
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        task.current_state_id = _state_id_for_status(db, task, status)
        db.commit()
    finally:
        db.close()


def _state_id_for_status(db, item, status: str) -> int:
    action_by_status = {
        "in_processing": "claim",
        "completed": "complete",
        "canceled": "cancel",
    }
    if status == "pending_assignment":
        state_ids = {
            value
            for value, in db.query(WorkflowState.id).filter(
                WorkflowState.definition_id == item.workflow_definition_id,
                WorkflowState.category == "start",
            ).all()
        }
    else:
        state_ids = {
            value
            for value, in db.query(WorkflowTransition.to_state_id).filter(
                WorkflowTransition.definition_id == item.workflow_definition_id,
                WorkflowTransition.action_key == action_by_status[status],
            ).all()
        }
    assert len(state_ids) == 1
    return next(iter(state_ids))


def _set_item_state_category(model, item_id: int, category: str) -> None:
    db = SessionLocal()
    try:
        item = db.query(model).filter(model.id == item_id).first()
        state = WorkflowState(
            definition_id=item.workflow_definition_id,
            status_name="测试终态" if category == "terminal" else "测试处理中",
            category=category,
            enabled=True,
        )
        db.add(state)
        db.flush()
        item.current_state_id = state.id
        db.commit()
    finally:
        db.close()


def test_iteration_crud_persists_to_database(client: TestClient):
    project_id = _create_project(client)

    created = client.post(
        "/api/v1/iterations",
        json={"project_id": project_id, "name": "MVP 迭代", "goal": "完成主链路"},
    )
    assert created.status_code == 200
    iteration_id = created.json()["id"]
    assert created.json()["project_id"] == project_id

    updated = client.patch(
        f"/api/v1/iterations/{iteration_id}",
        json={"goal": "Updated goal"},
    )
    assert updated.status_code == 200
    assert "status" not in updated.json()
    assert updated.json()["state_category"] == "start"
    assert updated.json()["goal"] == "Updated goal"

    deleted = client.delete(f"/api/v1/iterations/{iteration_id}")
    assert deleted.status_code == 204


def test_iteration_detail_collects_scoped_projects_and_linked_objects(client: TestClient):
    root_project = _create_project(client, "Root project")
    child_project = _create_project(client, "Child project", parent_id=root_project)
    other_project = _create_project(client, "Other project")
    iteration_id = _create_iteration(client, [root_project], "Scoped iteration")

    root_requirement = _create_requirement(client, root_project, "Root requirement")
    child_requirement = _create_requirement(client, child_project, "Child requirement")
    other_requirement = _create_requirement(client, other_project, "Other requirement")
    root_task = _create_task(client, root_project, "Root task", requirement_id=root_requirement)
    child_task = _create_task(client, child_project, "Child task")
    _create_task(client, other_project, "Other task")
    _create_case(client, child_project, child_requirement, "Child case")
    _create_bug(client, root_project, iteration_id, "Root bug")

    linked_requirements = client.post(
        f"/api/v1/iterations/{iteration_id}/requirements",
        json={"requirement_ids": [root_requirement, child_requirement]},
    )
    linked_tasks = client.post(
        f"/api/v1/iterations/{iteration_id}/tasks",
        json={"task_ids": [child_task]},
    )
    assert linked_requirements.status_code == 200
    assert linked_tasks.status_code == 200

    detail = client.get(f"/api/v1/iterations/{iteration_id}/detail")
    assert detail.status_code == 200
    requirement_ids = {item["id"] for item in detail.json()["requirements"]}
    task_ids = {item["id"] for item in detail.json()["tasks"]}
    project_names = {
        detail.json()["projects"][0]["name"],
        *[child["name"] for child in detail.json()["projects"][0]["children"]],
    }

    assert root_requirement in requirement_ids
    assert child_requirement in requirement_ids
    assert other_requirement not in requirement_ids
    assert root_task in task_ids
    assert child_task in task_ids
    assert project_names == {"Root project", "Child project"}


def test_iteration_job_auto_starts_without_changing_child_item_statuses(client: TestClient):
    project_id = _create_project(client)
    iteration_id = _create_iteration(client, [project_id], "Auto start iteration", status="planning")
    update = client.patch(f"/api/v1/iterations/{iteration_id}", json={"start_date": "2026-06-01"})
    assert update.status_code == 200

    requirement_id = _create_requirement(client, project_id, "Auto start requirement")
    task_id = _create_task(client, project_id, "Auto start task")
    assert client.post(f"/api/v1/iterations/{iteration_id}/requirements", json={"requirement_ids": [requirement_id]}).status_code == 200
    assert client.post(f"/api/v1/iterations/{iteration_id}/tasks", json={"task_ids": [task_id]}).status_code == 200

    started_count = run_auto_start_due_iterations()
    detail = client.get(f"/api/v1/iterations/{iteration_id}/detail")

    assert started_count == 1
    assert detail.status_code == 200
    assert "status" not in detail.json()["iteration"]
    assert detail.json()["iteration"]["state_category"] == "normal"
    assert detail.json()["iteration"]["actual_start_date"] == "2026-06-01"
    assert client.get(f"/api/v1/requirements/{requirement_id}").json()["state_category"] == "start"
    assert client.get(f"/api/v1/tasks/{task_id}").json()["state_category"] == "start"


def test_iteration_start_keeps_child_work_items_on_their_own_workflows(client: TestClient):
    project_id = _create_project(client)
    iteration_id = _create_iteration(client, [project_id])
    requirement_id = _create_requirement(client, project_id, "Requirement for iteration start")
    canceled_requirement_id = _create_requirement(client, project_id, "Canceled requirement", owner_id=1)
    _set_requirement_status(canceled_requirement_id, "canceled")

    requirement_task_id = _create_task(client, project_id, "Task under requirement", requirement_id=requirement_id)
    standalone_task_id = _create_task(client, project_id, "Standalone task linked to iteration")
    canceled_task_id = _create_task(client, project_id, "Canceled task", owner_id=1)
    _set_task_status(canceled_task_id, "canceled")

    assert client.post(
        f"/api/v1/iterations/{iteration_id}/requirements",
        json={"requirement_ids": [requirement_id, canceled_requirement_id]},
    ).status_code == 200
    assert client.post(
        f"/api/v1/iterations/{iteration_id}/tasks",
        json={"task_ids": [standalone_task_id, canceled_task_id]},
    ).status_code == 200

    started = client.post(
        f"/api/v1/workflow-runtime/iteration/{iteration_id}/transition",
        json={"action_key": "start", "payload": {"effective_time": "2026-06-12T09:30:00", "remark": "iteration kickoff"}},
    )

    assert started.status_code == 200
    assert client.get(f"/api/v1/requirements/{requirement_id}").json()["state_category"] == "start"
    assert client.get(f"/api/v1/requirements/{canceled_requirement_id}").json()["status_name"] == "已取消"
    assert client.get(f"/api/v1/tasks/{requirement_task_id}").json()["state_category"] == "start"
    assert client.get(f"/api/v1/tasks/{standalone_task_id}").json()["state_category"] == "start"
    assert client.get(f"/api/v1/tasks/{canceled_task_id}").json()["status_name"] == "已取消"


def test_iteration_finish_is_blocked_by_unfinished_direct_items(client: TestClient):
    project_id = _create_project(client)
    iteration_id = _create_iteration(client, [project_id], status="active")
    requirement_id = _create_requirement(client, project_id, "Open requirement")
    task_id = _create_task(client, project_id, "Open task")
    _create_bug(client, project_id, iteration_id, "Open bug")
    assert client.post(f"/api/v1/iterations/{iteration_id}/requirements", json={"requirement_ids": [requirement_id]}).status_code == 200
    assert client.post(f"/api/v1/iterations/{iteration_id}/tasks", json={"task_ids": [task_id]}).status_code == 200

    finished = client.post(
        f"/api/v1/workflow-runtime/iteration/{iteration_id}/transition",
        json={"action_key": "complete", "payload": {"effective_time": "2026-06-10T18:00:00"}},
    )

    assert finished.status_code == 400
    detail = finished.json()["detail"]
    assert detail["code"] == "ITERATION_HAS_OPEN_ITEMS"
    assert detail["counts"] == {"requirement": 1, "task": 1, "bug": 1, "test_run": 0}
    assert {(item["object_type"], item["title"]) for item in detail["items"]} == {
        ("requirement", "Open requirement"),
        ("task", "Open task"),
        ("bug", "Open bug"),
    }
    assert client.get(f"/api/v1/iterations/{iteration_id}/detail").json()["iteration"]["state_category"] == "normal"


def test_terminal_iteration_rejects_scope_mutations(client: TestClient):
    project_id = _create_project(client)
    iteration_id = _create_iteration(client, [project_id], status="active")
    linked_requirement_id = _create_requirement(client, project_id, "Terminal linked requirement")
    unplanned_requirement_id = _create_requirement(client, project_id, "Terminal new requirement")
    assert client.post(
        f"/api/v1/iterations/{iteration_id}/requirements",
        json={"requirement_ids": [linked_requirement_id]},
    ).status_code == 200
    _set_requirement_status(linked_requirement_id, "completed")
    completed = client.post(
        f"/api/v1/workflow-runtime/iteration/{iteration_id}/transition",
        json={"action_key": "complete", "payload": {"effective_time": "2026-07-21T18:00:00"}},
    )
    assert completed.status_code == 200

    responses = [
        client.patch(f"/api/v1/iterations/{iteration_id}", json={"name": "Changed terminal iteration"}),
        client.post(
            f"/api/v1/iterations/{iteration_id}/requirements",
            json={"requirement_ids": [unplanned_requirement_id]},
        ),
        client.delete(f"/api/v1/iterations/{iteration_id}/requirements/{linked_requirement_id}"),
    ]

    for response in responses:
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "ITERATION_NOT_MUTABLE"


def test_terminal_iteration_rejects_ordinary_work_item_updates_and_deletes(client: TestClient):
    project_id = _create_project(client)
    iteration_id = _create_iteration(client, [project_id])
    requirement_id = _create_requirement(client, project_id, "Immutable requirement")
    task_id = _create_task(client, project_id, "Immutable task")
    bug_id = _create_bug(client, project_id, iteration_id, "Immutable bug")
    assert client.post(
        f"/api/v1/iterations/{iteration_id}/requirements",
        json={"requirement_ids": [requirement_id]},
    ).status_code == 200
    assert client.post(
        f"/api/v1/iterations/{iteration_id}/tasks",
        json={"task_ids": [task_id]},
    ).status_code == 200
    _mark_iteration_terminal(iteration_id)

    for endpoint, object_id in (
        ("requirements", requirement_id),
        ("tasks", task_id),
        ("bugs", bug_id),
    ):
        for payload in ({"title": "Forbidden title"}, {"owner_id": None}):
            response = client.patch(f"/api/v1/{endpoint}/{object_id}", json=payload)
            assert response.status_code == 409, (endpoint, payload, response.text)
            assert response.json()["detail"]["code"] == "ITERATION_NOT_MUTABLE"

        deleted = client.delete(f"/api/v1/{endpoint}/{object_id}")
        assert deleted.status_code == 409, (endpoint, deleted.text)
        assert deleted.json()["detail"]["code"] == "ITERATION_NOT_MUTABLE"


def test_terminal_iteration_rejects_test_run_create_update_move_and_delete(client: TestClient):
    project_id = _create_project(client)
    terminal_iteration_id = _create_iteration(client, [project_id])
    active_iteration_id = _create_iteration(client, [project_id])
    movable_run = client.post(
        "/api/v1/test-runs",
        json={"project_id": project_id, "iteration_id": active_iteration_id, "name": "Movable test run", "status": "completed"},
    )
    assert movable_run.status_code == 200
    terminal_run = client.post(
        "/api/v1/test-runs",
        json={"project_id": project_id, "iteration_id": terminal_iteration_id, "name": "Terminal test run", "status": "completed"},
    )
    assert terminal_run.status_code == 200
    _mark_iteration_terminal(terminal_iteration_id)

    responses = [
        client.post(
            "/api/v1/test-runs",
            json={"project_id": project_id, "iteration_id": terminal_iteration_id, "name": "Forbidden test run"},
        ),
        client.patch(f"/api/v1/test-runs/{terminal_run.json()['id']}", json={"name": "Forbidden rename"}),
        client.delete(f"/api/v1/test-runs/{terminal_run.json()['id']}"),
        client.patch(f"/api/v1/test-runs/{movable_run.json()['id']}", json={"iteration_id": terminal_iteration_id}),
    ]

    for response in responses:
        assert response.status_code == 409, response.text
        assert response.json()["detail"]["code"] == "ITERATION_NOT_MUTABLE"


def test_iteration_project_scope_removal_closes_work_item_history_with_actor_and_reason(client: TestClient):
    retained_project_id = _create_project(client, "Retained project")
    removed_project_id = _create_project(client, "Removed project")
    iteration_id = _create_iteration(client, [retained_project_id, removed_project_id])
    requirement_id = _create_requirement(client, removed_project_id, "Removed requirement")
    task_id = _create_task(client, removed_project_id, "Removed task")
    bug_id = _create_bug(client, removed_project_id, iteration_id, "Removed bug")
    assert client.post(
        f"/api/v1/iterations/{iteration_id}/requirements",
        json={"requirement_ids": [requirement_id]},
    ).status_code == 200
    assert client.post(
        f"/api/v1/iterations/{iteration_id}/tasks",
        json={"task_ids": [task_id]},
    ).status_code == 200

    updated = client.patch(
        f"/api/v1/iterations/{iteration_id}",
        json={"project_ids": [retained_project_id]},
    )

    assert updated.status_code == 200, updated.text
    db = SessionLocal()
    try:
        assert db.query(Requirement).filter(Requirement.id == requirement_id).one().iteration_id is None
        assert db.query(Task).filter(Task.id == task_id).one().iteration_id is None
        assert db.query(Bug).filter(Bug.id == bug_id).one().iteration_id is None
        histories = db.query(WorkItemIterationHistory).filter(
            WorkItemIterationHistory.iteration_id == iteration_id,
            WorkItemIterationHistory.object_id.in_([requirement_id, task_id, bug_id]),
        ).all()
        assert len(histories) == 3
        assert all(row.left_at is not None for row in histories)
        assert all(row.left_by is not None for row in histories)
        assert {row.leave_reason for row in histories} == {"iteration_project_scope_removed"}
    finally:
        db.close()


def test_iteration_cancel_uses_runtime_and_complete_gate(client: TestClient):
    project_id = _create_project(client)
    iteration_id = _create_iteration(client, [project_id], status="active")
    requirement_id = _create_requirement(client, project_id, "Cancel blocker")
    assert client.post(
        f"/api/v1/iterations/{iteration_id}/requirements",
        json={"requirement_ids": [requirement_id]},
    ).status_code == 200

    blocked = client.post(
        f"/api/v1/workflow-runtime/iteration/{iteration_id}/transition",
        json={"action_key": "cancel", "payload": {"remark": "cancel blocked"}},
    )
    assert blocked.status_code == 400
    assert client.get(f"/api/v1/iterations/{iteration_id}/detail").json()["iteration"]["state_category"] == "normal"

    _set_requirement_status(requirement_id, "completed")
    canceled = client.post(
        f"/api/v1/workflow-runtime/iteration/{iteration_id}/transition",
        json={"action_key": "cancel", "payload": {"remark": "cancel approved"}},
    )

    assert canceled.status_code == 200
    assert "status" not in canceled.json()
    assert canceled.json()["state_category"] == "terminal"
    snapshot = client.get(f"/api/v1/iterations/{iteration_id}/detail").json()["completion_snapshot"]
    assert snapshot["action"] == "cancel"
    assert snapshot["counts"]["requirement"] == 1


def test_iteration_finish_is_blocked_by_open_bug_without_other_work_items(client: TestClient):
    project_id = _create_project(client)
    iteration_id = _create_iteration(client, [project_id], status="active")
    _create_bug(client, project_id, iteration_id, "Only open bug")

    finished = client.post(
        f"/api/v1/workflow-runtime/iteration/{iteration_id}/transition",
        json={"action_key": "complete", "payload": {"effective_time": "2026-06-10T18:00:00"}},
    )

    assert finished.status_code == 400
    detail = client.get(f"/api/v1/iterations/{iteration_id}/detail").json()
    assert detail["iteration"]["state_category"] == "normal"
    assert detail["completion_snapshot"] is None


def test_terminal_iteration_detail_uses_persisted_completion_snapshot(client: TestClient):
    project_id = _create_project(client)
    iteration_id = _create_iteration(client, [project_id], status="active")
    requirement_id = _create_requirement(client, project_id, "Snapshot requirement", owner_id=1)
    task_id = _create_task(client, project_id, "Snapshot task", owner_id=1)
    assert client.post(
        f"/api/v1/iterations/{iteration_id}/requirements",
        json={"requirement_ids": [requirement_id]},
    ).status_code == 200
    assert client.post(
        f"/api/v1/iterations/{iteration_id}/tasks",
        json={"task_ids": [task_id]},
    ).status_code == 200
    _set_requirement_status(requirement_id, "completed")
    _set_task_status(task_id, "completed")

    completed = client.post(
        f"/api/v1/workflow-runtime/iteration/{iteration_id}/transition",
        json={"action_key": "complete", "payload": {"effective_time": "2026-07-22T12:00:00"}},
    )

    assert completed.status_code == 200, completed.text
    detail = client.get(f"/api/v1/iterations/{iteration_id}/detail").json()
    snapshot = detail["completion_snapshot"]
    assert snapshot["action"] == "complete"
    assert snapshot["operation_log_id"]
    assert snapshot["counts"] == {"requirement": 1, "task": 1, "bug": 0, "test_run": 0}
    assert snapshot["items"]["requirement"] == [{
        "id": requirement_id,
        "title": "Snapshot requirement",
        "state_id": detail["requirements"][0]["current_state_id"],
        "status_name": detail["requirements"][0]["status_name"],
        "owner_id": 1,
    }]
    assert detail["metrics"]["requirement_total"] == 1

    db = SessionLocal()
    try:
        db.query(Requirement).filter(Requirement.id == requirement_id).update({Requirement.iteration_id: None})
        db.commit()
    finally:
        db.close()

    historical_detail = client.get(f"/api/v1/iterations/{iteration_id}/detail").json()
    assert historical_detail["metrics"]["requirement_total"] == 1
    assert historical_detail["completion_snapshot"]["items"]["requirement"][0]["id"] == requirement_id


def test_terminal_iteration_detail_exposes_all_headline_totals_from_snapshot(client: TestClient):
    project_id = _create_project(client)
    iteration_id = _create_iteration(client, [project_id], status="active")
    test_run = client.post(
        "/api/v1/test-runs",
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
            "name": "Completed snapshot test run",
            "status": "completed",
        },
    )
    assert test_run.status_code == 200

    completed = client.post(
        f"/api/v1/workflow-runtime/iteration/{iteration_id}/transition",
        json={"action_key": "complete", "payload": {"effective_time": "2026-07-22T12:00:00"}},
    )
    assert completed.status_code == 200, completed.text

    detail = client.get(f"/api/v1/iterations/{iteration_id}/detail").json()
    assert detail["completion_snapshot"]["counts"]["test_run"] == 1
    assert detail["completion_snapshot"]["terminal_counts"]["test_run"] == 1
    assert detail["metrics"]["test_run_total"] == 1
    assert detail["metrics"]["closed_test_run_total"] == 1


def test_iteration_finish_is_blocked_by_open_test_run(client: TestClient):
    project_id = _create_project(client)
    iteration_id = _create_iteration(client, [project_id], status="active")
    test_run = client.post(
        "/api/v1/test-runs",
        json={
            "project_id": project_id,
            "iteration_id": iteration_id,
            "name": "Open iteration test run",
            "status": "running",
        },
    )
    assert test_run.status_code == 200

    finished = client.post(
        f"/api/v1/workflow-runtime/iteration/{iteration_id}/transition",
        json={"action_key": "complete", "payload": {"effective_time": "2026-06-10T18:00:00"}},
    )

    assert finished.status_code == 400


def test_iteration_finish_checks_only_directly_included_tasks(client: TestClient):
    project_id = _create_project(client)
    iteration_id = _create_iteration(client, [project_id], status="active")
    requirement_id = _create_requirement(client, project_id, "Completed direct requirement")
    linked_task_id = _create_task(
        client,
        project_id,
        "Open task linked only through requirement",
        requirement_id=requirement_id,
    )
    assert client.post(
        f"/api/v1/iterations/{iteration_id}/requirements",
        json={"requirement_ids": [requirement_id]},
    ).status_code == 200
    _set_requirement_status(requirement_id, "completed")

    finished = client.post(
        f"/api/v1/workflow-runtime/iteration/{iteration_id}/transition",
        json={"action_key": "complete", "payload": {"effective_time": "2026-06-10T18:00:00"}},
    )

    assert finished.status_code == 200
    assert client.get(f"/api/v1/tasks/{linked_task_id}").json()["state_category"] == "start"


def test_iteration_defer_moves_selected_unfinished_items(client: TestClient):
    project_id = _create_project(client)
    current_iteration_id = _create_iteration(client, [project_id], "Current iteration", status="active")
    target_iteration_id = _create_iteration(client, [project_id], "Target iteration", status="planning")
    requirement_id = _create_requirement(client, project_id, "Deferred requirement")
    task_id = _create_task(client, project_id, "Deferred task")
    assert client.post(f"/api/v1/iterations/{current_iteration_id}/requirements", json={"requirement_ids": [requirement_id]}).status_code == 200
    assert client.post(f"/api/v1/iterations/{current_iteration_id}/tasks", json={"task_ids": [task_id]}).status_code == 200
    _set_requirement_status(requirement_id, "in_processing")
    _set_task_status(task_id, "in_processing")

    deferred = client.post(
        f"/api/v1/iterations/{current_iteration_id}/defer-work-items",
        json={"target_iteration_id": target_iteration_id, "requirement_ids": [requirement_id], "task_ids": [task_id]},
    )

    assert deferred.status_code == 200
    assert deferred.json()["moved_requirement_ids"] == [requirement_id]
    assert deferred.json()["moved_task_ids"] == [task_id]
    assert client.get(f"/api/v1/iterations/{target_iteration_id}/detail").status_code == 200


def test_iteration_defer_rejects_completed_and_canceled_items(client: TestClient):
    project_id = _create_project(client)
    current_iteration_id = _create_iteration(client, [project_id], "Current terminal iteration", status="active")
    target_iteration_id = _create_iteration(client, [project_id], "Target terminal iteration", status="planning")
    requirement_id = _create_requirement(client, project_id, "Completed requirement")
    task_id = _create_task(client, project_id, "Canceled task")
    assert client.post(
        f"/api/v1/iterations/{current_iteration_id}/requirements",
        json={"requirement_ids": [requirement_id]},
    ).status_code == 200
    assert client.post(
        f"/api/v1/iterations/{current_iteration_id}/tasks",
        json={"task_ids": [task_id]},
    ).status_code == 200
    _set_requirement_status(requirement_id, "completed")
    _set_task_status(task_id, "canceled")

    deferred = client.post(
        f"/api/v1/iterations/{current_iteration_id}/defer-work-items",
        json={"target_iteration_id": target_iteration_id, "requirement_ids": [requirement_id], "task_ids": [task_id]},
    )

    assert deferred.status_code == 400


def test_iteration_progress_counts_default_template_terminal_requirements(client: TestClient):
    project_id = _create_project(client)
    iteration_id = _create_iteration(client, [project_id])
    requirement_id = _create_requirement(client, project_id, "Completed progress requirement")
    assert client.post(
        f"/api/v1/iterations/{iteration_id}/requirements",
        json={"requirement_ids": [requirement_id]},
    ).status_code == 200
    _set_requirement_status(requirement_id, "completed")

    detail = client.get(f"/api/v1/iterations/{iteration_id}/detail")

    assert detail.status_code == 200
    assert detail.json()["metrics"]["closed_requirement_total"] == 1
    assert detail.json()["metrics"]["progress_rate"] == 1.0


def test_iteration_progress_uses_current_state_category(client: TestClient):
    project_id = _create_project(client)
    iteration_id = _create_iteration(client, [project_id])
    requirement_id = _create_requirement(client, project_id, "State category progress requirement")
    assert client.post(
        f"/api/v1/iterations/{iteration_id}/requirements",
        json={"requirement_ids": [requirement_id]},
    ).status_code == 200
    _set_item_state_category(Requirement, requirement_id, "terminal")

    detail = client.get(f"/api/v1/iterations/{iteration_id}/detail")

    assert detail.status_code == 200
    assert detail.json()["metrics"]["closed_requirement_total"] == 1
    assert detail.json()["metrics"]["progress_rate"] == 1.0
    listed = next(item for item in detail.json()["requirements"] if item["id"] == requirement_id)
    assert listed["status_name"] == "测试终态"
    assert listed["state_category"] == "terminal"
