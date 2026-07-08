from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.jobs.iteration_jobs import run_auto_start_due_iterations
from app.models.requirement import Requirement
from app.models.user import User


def _create_project(client: TestClient, name: str | None = None, parent_id: int | None = None) -> int:
    payload = {"name": name or f"Project-{uuid4().hex[:8]}"}
    if parent_id:
        payload["parent_id"] = parent_id
    response = client.post("/api/v1/projects", json=payload)
    assert response.status_code == 200
    return response.json()["id"]


def _create_user(client: TestClient, username: str | None = None, full_name: str | None = None) -> int:
    suffix = uuid4().hex[:8]
    db = SessionLocal()
    try:
        user = User(
            username=username or f"user_{suffix}",
            full_name=full_name or f"User {suffix}",
            password_hash="test",
            department="QA",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id
    finally:
        db.close()


def _create_iteration(client: TestClient, project_ids: list[int], name: str | None = None) -> int:
    response = client.post(
        "/api/v1/iterations",
        json={"project_ids": project_ids, "name": name or f"Iteration-{uuid4().hex[:8]}", "status": "planning"},
    )
    assert response.status_code == 200
    return response.json()["id"]


def _create_requirement(client: TestClient, project_id: int, title: str | None = None, status: str = "draft") -> int:
    response = client.post(
        "/api/v1/requirements",
        json={"project_id": project_id, "title": title or f"Requirement-{uuid4().hex[:8]}", "status": status},
    )
    assert response.status_code == 200
    requirement_id = response.json()["id"]
    if status == "closed":
        close_response = client.post(
            f"/api/v1/requirements/{requirement_id}/close",
            json={"reason": "done", "remark": "closed for iteration metric"},
        )
        assert close_response.status_code == 200
    elif status == "done":
        db = SessionLocal()
        try:
            requirement = db.query(Requirement).filter(Requirement.id == requirement_id).first()
            requirement.status = "done"
            db.commit()
        finally:
            db.close()
    return requirement_id


def _create_task(
    client: TestClient,
    project_id: int,
    title: str | None = None,
    requirement_id: int | None = None,
) -> int:
    payload = {"project_id": project_id, "title": title or f"Task-{uuid4().hex[:8]}", "status": "todo"}
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


def _create_bug(client: TestClient, project_id: int, iteration_id: int, title: str | None = None) -> int:
    response = client.post(
        "/api/v1/bugs",
        json={"project_id": project_id, "iteration_id": iteration_id, "title": title or f"Bug-{uuid4().hex[:8]}"},
    )
    assert response.status_code == 200
    return response.json()["id"]


def _flatten_project_names(projects: list[dict]) -> list[str]:
    names = []
    for project in projects:
        names.append(project["name"])
        names.extend(_flatten_project_names(project.get("children") or []))
    return names


def test_iteration_detail_links_requirements_tasks_and_metrics(client: TestClient):
    root_project = _create_project(client, "Root Project")
    child_project = _create_project(client, "Child Project", parent_id=root_project)
    other_project = _create_project(client, "Other Project")
    iteration_id = _create_iteration(client, [root_project])

    root_req = _create_requirement(client, root_project, "Root requirement", status="closed")
    child_req = _create_requirement(client, child_project, "Child requirement")
    other_req = _create_requirement(client, other_project, "Other requirement")
    root_task = _create_task(client, root_project, "Root task", requirement_id=root_req)
    child_task = _create_task(client, child_project, "Child standalone task")
    other_task = _create_task(client, other_project, "Other task")
    case_id = _create_case(client, root_project, root_req, "Root case")

    available_requirements = client.get(f"/api/v1/iterations/{iteration_id}/available-requirements")
    assert available_requirements.status_code == 200
    assert {item["id"] for item in available_requirements.json()} == {root_req, child_req}
    assert other_req not in {item["id"] for item in available_requirements.json()}

    linked_requirements = client.post(
        f"/api/v1/iterations/{iteration_id}/requirements",
        json={"requirement_ids": [root_req, child_req]},
    )
    assert linked_requirements.status_code == 200

    available_tasks = client.get(f"/api/v1/iterations/{iteration_id}/available-tasks")
    assert available_tasks.status_code == 200
    assert {item["id"] for item in available_tasks.json()} == {child_task}
    assert other_task not in {item["id"] for item in available_tasks.json()}

    linked_tasks = client.post(f"/api/v1/iterations/{iteration_id}/tasks", json={"task_ids": [child_task]})
    assert linked_tasks.status_code == 200

    detail = client.get(f"/api/v1/iterations/{iteration_id}/detail")
    assert detail.status_code == 200
    data = detail.json()
    assert {item["id"] for item in data["requirements"]} == {root_req, child_req}
    assert {item["id"] for item in data["tasks"]} == {root_task, child_task}
    assert {item["id"] for item in data["test_cases"]} == {case_id}
    assert "owner_id" in data["projects"][0]
    assert data["metrics"]["requirement_total"] == 2
    assert data["metrics"]["closed_requirement_total"] == 1
    assert data["metrics"]["progress_rate"] == 0.5
    assert data["metrics"]["covered_requirement_total"] == 1
    assert data["metrics"]["test_coverage_rate"] == 0.5

    second_iteration_id = _create_iteration(client, [root_project], "Second iteration")
    unavailable = client.get(f"/api/v1/iterations/{second_iteration_id}/available-requirements")
    assert unavailable.status_code == 200
    assert root_req not in {item["id"] for item in unavailable.json()}
    assert child_req not in {item["id"] for item in unavailable.json()}

    removed_requirement = client.delete(f"/api/v1/iterations/{iteration_id}/requirements/{root_req}")
    assert removed_requirement.status_code == 204
    detail_after_requirement_remove = client.get(f"/api/v1/iterations/{iteration_id}/detail").json()
    assert root_req not in {item["id"] for item in detail_after_requirement_remove["requirements"]}
    assert root_task not in {item["id"] for item in detail_after_requirement_remove["tasks"]}

    removed_task = client.delete(f"/api/v1/iterations/{iteration_id}/tasks/{child_task}")
    assert removed_task.status_code == 204
    detail_after_task_remove = client.get(f"/api/v1/iterations/{iteration_id}/detail").json()
    assert child_task not in {item["id"] for item in detail_after_task_remove["tasks"]}


def test_iteration_detail_project_tree_does_not_duplicate_child_projects(client: TestClient):
    root_project = _create_project(client, "InnovateX operations")
    child_project = _create_project(client, "Material management", parent_id=root_project)
    iteration_id = _create_iteration(client, [root_project], "Iteration 1.4.6")
    child_requirement = _create_requirement(client, child_project, "Material approval requirement")

    linked_requirements = client.post(
        f"/api/v1/iterations/{iteration_id}/requirements",
        json={"requirement_ids": [child_requirement]},
    )
    assert linked_requirements.status_code == 200

    detail = client.get(f"/api/v1/iterations/{iteration_id}/detail")

    assert detail.status_code == 200
    project_names = _flatten_project_names(detail.json()["projects"])
    assert project_names.count("InnovateX operations") == 1
    assert project_names.count("Material management") == 1


def test_generated_task_for_linked_requirement_appears_in_iteration_detail(client: TestClient):
    project_id = _create_project(client)
    iteration_id = _create_iteration(client, [project_id])
    requirement_id = _create_requirement(client, project_id, "Linked requirement")

    linked_requirements = client.post(
        f"/api/v1/iterations/{iteration_id}/requirements",
        json={"requirement_ids": [requirement_id]},
    )
    assert linked_requirements.status_code == 200

    generated = client.post(
        f"/api/v1/requirements/{requirement_id}/generate-task",
        json={"title": "Generated task from iteration requirement", "task_type": "development"},
    )
    assert generated.status_code == 200
    task_id = generated.json()["id"]

    detail = client.get(f"/api/v1/iterations/{iteration_id}/detail")
    assert detail.status_code == 200
    tasks = detail.json()["tasks"]
    assert {item["id"] for item in tasks} == {task_id}
    assert tasks[0]["requirement_id"] == requirement_id
    assert tasks[0]["project_id"] == project_id


def test_iteration_project_scope_update_unlinks_out_of_scope_work_items(client: TestClient):
    removed_project = _create_project(client, "Removed linked item project")
    current_project = _create_project(client, "Current iteration project")
    iteration_id = _create_iteration(client, [removed_project, current_project])
    requirement_id = _create_requirement(client, removed_project, "Requirement removed from iteration scope")
    task_id = _create_task(client, removed_project, "Direct task removed from iteration scope")
    case_id = _create_case(client, removed_project, requirement_id, "Case removed from iteration scope")
    bug_id = _create_bug(client, removed_project, iteration_id, "Bug removed from iteration scope")
    linked_requirements = client.post(
        f"/api/v1/iterations/{iteration_id}/requirements",
        json={"requirement_ids": [requirement_id]},
    )
    assert linked_requirements.status_code == 200
    linked_tasks = client.post(f"/api/v1/iterations/{iteration_id}/tasks", json={"task_ids": [task_id]})
    assert linked_tasks.status_code == 200

    updated = client.patch(f"/api/v1/iterations/{iteration_id}", json={"project_ids": [current_project]})
    assert updated.status_code == 200

    detail = client.get(f"/api/v1/iterations/{iteration_id}/detail")

    assert detail.status_code == 200
    project_ids = {item["id"] for item in detail.json()["projects"]}
    assert removed_project not in project_ids
    assert current_project in project_ids
    assert requirement_id not in {item["id"] for item in detail.json()["requirements"]}
    assert task_id not in {item["id"] for item in detail.json()["tasks"]}
    assert case_id not in {item["id"] for item in detail.json()["test_cases"]}
    assert bug_id not in {item["id"] for item in detail.json()["bugs"]}
    assert client.get(f"/api/v1/requirements/{requirement_id}").json()["iteration_id"] is None
    assert client.get(f"/api/v1/tasks/{task_id}").json()["iteration_id"] is None
    assert client.get(f"/api/v1/test-cases/{case_id}").json()["iteration_id"] is None
    assert client.get(f"/api/v1/bugs/{bug_id}").json()["iteration_id"] is None


def test_iteration_can_bind_child_project_after_project_tree_move(client: TestClient):
    platform_project = _create_project(client, "InnovateX platform")
    archive_project = _create_project(client, "QA archive management")
    operations_project = _create_project(client, "InnovateX operations")

    moved_project = client.patch(
        f"/api/v1/projects/{archive_project}",
        json={"name": "QA archive management", "parent_id": operations_project},
    )
    assert moved_project.status_code == 200
    assert moved_project.json()["parent_id"] == operations_project

    iteration_response = client.post(
        "/api/v1/iterations",
        json={
            "project_ids": [archive_project],
            "name": "QA archive maintenance iteration",
            "status": "planning",
        },
    )
    assert iteration_response.status_code == 200
    iteration_id = iteration_response.json()["id"]
    assert iteration_response.json()["project_ids"] == [archive_project]

    requirement_id = _create_requirement(client, archive_project, "QA archive maintenance requirement")
    linked_requirement = client.post(
        f"/api/v1/iterations/{iteration_id}/requirements",
        json={"requirement_ids": [requirement_id]},
    )
    assert linked_requirement.status_code == 200

    standalone_task_id = _create_task(client, archive_project, "QA archive standalone maintenance task")
    linked_task = client.post(f"/api/v1/iterations/{iteration_id}/tasks", json={"task_ids": [standalone_task_id]})
    assert linked_task.status_code == 200

    detail = client.get(f"/api/v1/iterations/{iteration_id}/detail")
    assert detail.status_code == 200
    data = detail.json()
    assert data["iteration"]["project_ids"] == [archive_project]
    assert {item["id"] for item in data["requirements"]} == {requirement_id}
    assert {item["id"] for item in data["tasks"]} == {standalone_task_id}
    assert archive_project in data["scoped_project_ids"]
    assert platform_project not in data["scoped_project_ids"]


def test_generate_task_accepts_default_owner_from_iteration_page(client: TestClient):
    owner_id = _create_user(client)
    project_id = _create_project(client)
    requirement_id = _create_requirement(client, project_id, "Requirement without owner")

    generated = client.post(
        f"/api/v1/requirements/{requirement_id}/generate-task",
        json={"title": "Generated task with project owner", "owner_id": owner_id},
    )

    assert generated.status_code == 200
    assert generated.json()["owner_id"] == owner_id


def test_iteration_can_start_with_actual_start_date(client: TestClient):
    project_id = _create_project(client)
    iteration_id = _create_iteration(client, [project_id])

    started = client.post(
        f"/api/v1/iterations/{iteration_id}/start",
        json={"effective_time": "2026-06-12T09:30:00", "remark": "iteration kickoff"},
    )
    assert started.status_code == 200
    data = started.json()
    assert data["status"] == "active"
    assert data["actual_start_date"] == "2026-06-12"

    operations = client.get(f"/api/v1/iterations/{iteration_id}/status-operations")
    assert operations.status_code == 200
    assert operations.json()[0]["action"] == "start"
    assert operations.json()[0]["from_status"] == "planning"
    assert operations.json()[0]["to_status"] == "active"
    assert operations.json()[0]["remark"] == "iteration kickoff"


def test_iteration_job_auto_starts_when_start_date_is_reached(client: TestClient):
    project_id = _create_project(client)
    created = client.post(
        "/api/v1/iterations",
        json={
            "project_ids": [project_id],
            "name": f"Auto start iteration-{uuid4().hex[:8]}",
            "status": "planning",
            "start_date": "2026-06-01",
        },
    )
    assert created.status_code == 200
    iteration_id = created.json()["id"]
    requirement_id = _create_requirement(client, project_id, "Auto start requirement")
    task_id = _create_task(client, project_id, "Auto start task")
    linked_requirement = client.post(
        f"/api/v1/iterations/{iteration_id}/requirements",
        json={"requirement_ids": [requirement_id]},
    )
    assert linked_requirement.status_code == 200
    linked_task = client.post(f"/api/v1/iterations/{iteration_id}/tasks", json={"task_ids": [task_id]})
    assert linked_task.status_code == 200

    started_count = run_auto_start_due_iterations()
    detail = client.get(f"/api/v1/iterations/{iteration_id}/detail")

    assert started_count == 1
    assert detail.status_code == 200
    assert detail.json()["iteration"]["status"] == "active"
    assert detail.json()["iteration"]["actual_start_date"] == "2026-06-01"
    assert client.get(f"/api/v1/requirements/{requirement_id}").json()["status"] == "active"
    assert client.get(f"/api/v1/tasks/{task_id}").json()["status"] == "doing"
    operations = client.get(f"/api/v1/iterations/{iteration_id}/status-operations").json()
    assert operations[0]["action"] == "start"
    assert operations[0]["remark"] == "到达计划开始日期自动开始"


def test_iteration_list_does_not_auto_start_before_start_date(client: TestClient):
    project_id = _create_project(client)
    created = client.post(
        "/api/v1/iterations",
        json={
            "project_ids": [project_id],
            "name": f"Future iteration-{uuid4().hex[:8]}",
            "status": "planning",
            "start_date": "2099-06-01",
        },
    )
    assert created.status_code == 200

    listed = client.get("/api/v1/iterations")

    assert listed.status_code == 200
    iteration = next(item for item in listed.json() if item["id"] == created.json()["id"])
    assert iteration["status"] == "planning"
    assert iteration["actual_start_date"] is None


def test_iteration_start_activates_open_requirements_and_tasks(client: TestClient):
    project_id = _create_project(client)
    iteration_id = _create_iteration(client, [project_id])
    requirement_id = _create_requirement(client, project_id, "Draft requirement for iteration start")
    closed_requirement_id = _create_requirement(client, project_id, "Closed requirement remains closed", status="closed")
    requirement_task_id = _create_task(client, project_id, "Task under draft requirement", requirement_id=requirement_id)
    standalone_task_id = _create_task(client, project_id, "Standalone task linked to iteration")
    closed_task_id = _create_task(client, project_id, "Closed task remains closed")
    closed_task = client.post(
        f"/api/v1/tasks/{closed_task_id}/close",
        json={"reason": "done", "remark": "closed before iteration start"},
    )
    assert closed_task.status_code == 200

    linked_requirements = client.post(
        f"/api/v1/iterations/{iteration_id}/requirements",
        json={"requirement_ids": [requirement_id, closed_requirement_id]},
    )
    assert linked_requirements.status_code == 200
    linked_tasks = client.post(
        f"/api/v1/iterations/{iteration_id}/tasks",
        json={"task_ids": [standalone_task_id, closed_task_id]},
    )
    assert linked_tasks.status_code == 200

    started = client.post(
        f"/api/v1/iterations/{iteration_id}/start",
        json={"effective_time": "2026-06-12T09:30:00", "remark": "iteration kickoff"},
    )

    assert started.status_code == 200
    assert client.get(f"/api/v1/requirements/{requirement_id}").json()["status"] == "active"
    assert client.get(f"/api/v1/requirements/{closed_requirement_id}").json()["status"] == "closed"
    assert client.get(f"/api/v1/tasks/{requirement_task_id}").json()["status"] == "doing"
    assert client.get(f"/api/v1/tasks/{standalone_task_id}").json()["status"] == "doing"
    assert client.get(f"/api/v1/tasks/{closed_task_id}").json()["status"] == "closed"

    requirement_history = client.get(f"/api/v1/requirements/{requirement_id}/status-operations").json()
    task_history = client.get(f"/api/v1/tasks/{standalone_task_id}/status-operations").json()
    assert requirement_history[-1]["action"] == "activate"
    assert requirement_history[-1]["remark"] == "迭代开始自动激活"
    assert task_history[-1]["action"] == "activate"
    assert task_history[-1]["remark"] == "迭代开始自动激活"


def test_iteration_can_finish_with_actual_end_date(client: TestClient):
    project_id = _create_project(client)
    iteration_id = _create_iteration(client, [project_id])
    started = client.post(
        f"/api/v1/iterations/{iteration_id}/start",
        json={"effective_time": "2026-06-12T09:30:00"},
    )
    assert started.status_code == 200

    finished = client.post(
        f"/api/v1/iterations/{iteration_id}/finish",
        json={"effective_time": "2026-06-20T18:00:00", "remark": "iteration finish"},
    )

    assert finished.status_code == 200
    data = finished.json()
    assert data["status"] == "finished"
    assert data["actual_end_date"] == "2026-06-20"

    operations = client.get(f"/api/v1/iterations/{iteration_id}/status-operations")
    assert operations.status_code == 200
    assert operations.json()[-1]["action"] == "finish"
    assert operations.json()[-1]["from_status"] == "active"
    assert operations.json()[-1]["to_status"] == "finished"
    assert operations.json()[-1]["remark"] == "iteration finish"


def test_iteration_finish_rejects_unfinished_requirements_and_tasks(client: TestClient):
    project_id = _create_project(client)
    iteration_id = _create_iteration(client, [project_id])
    requirement_id = _create_requirement(client, project_id, "Unfinished requirement")
    task_id = _create_task(client, project_id, "Unfinished task")
    linked_requirements = client.post(
        f"/api/v1/iterations/{iteration_id}/requirements",
        json={"requirement_ids": [requirement_id]},
    )
    assert linked_requirements.status_code == 200
    linked_tasks = client.post(f"/api/v1/iterations/{iteration_id}/tasks", json={"task_ids": [task_id]})
    assert linked_tasks.status_code == 200
    started = client.post(
        f"/api/v1/iterations/{iteration_id}/start",
        json={"effective_time": "2026-06-12T09:30:00"},
    )
    assert started.status_code == 200

    finished = client.post(
        f"/api/v1/iterations/{iteration_id}/finish",
        json={"effective_time": "2026-06-20T18:00:00", "remark": "iteration finish"},
    )

    assert finished.status_code == 400
    assert "存在未完成需求 1 个" in finished.json()["detail"]
    assert "存在未完成任务 1 个" in finished.json()["detail"]
    assert "Unfinished requirement" in finished.json()["detail"]
    assert "Unfinished task" in finished.json()["detail"]


def test_iteration_finish_allows_done_requirements(client: TestClient):
    project_id = _create_project(client, "Finish done requirements project")
    requirement_id = _create_requirement(client, project_id, "Finished requirement", status="done")
    iteration_id = _create_iteration(client, [project_id], "Finish done requirements iteration")
    linked = client.post(
        f"/api/v1/iterations/{iteration_id}/requirements",
        json={"requirement_ids": [requirement_id]},
    )
    assert linked.status_code == 200
    started = client.post(f"/api/v1/iterations/{iteration_id}/start", json={"effective_time": "2026-06-01T09:00:00"})
    assert started.status_code == 200

    finished = client.post(f"/api/v1/iterations/{iteration_id}/finish", json={"effective_time": "2026-06-10T18:00:00"})

    assert finished.status_code == 200
    assert finished.json()["status"] == "finished"


def test_defer_unfinished_iteration_work_items_to_target_iteration(client: TestClient):
    project_id = _create_project(client)
    iteration_id = _create_iteration(client, [project_id], "Current iteration")
    target_iteration_id = _create_iteration(client, [project_id], "Next iteration")
    requirement_id = _create_requirement(client, project_id, "Deferred requirement")
    task_id = _create_task(client, project_id, "Deferred task")
    linked_requirements = client.post(
        f"/api/v1/iterations/{iteration_id}/requirements",
        json={"requirement_ids": [requirement_id]},
    )
    assert linked_requirements.status_code == 200
    linked_tasks = client.post(f"/api/v1/iterations/{iteration_id}/tasks", json={"task_ids": [task_id]})
    assert linked_tasks.status_code == 200
    started = client.post(
        f"/api/v1/iterations/{iteration_id}/start",
        json={"effective_time": "2026-06-12T09:30:00"},
    )
    assert started.status_code == 200

    deferred = client.post(
        f"/api/v1/iterations/{iteration_id}/defer-work-items",
        json={"target_iteration_id": target_iteration_id, "remark": "move to next iteration"},
    )

    assert deferred.status_code == 200
    assert deferred.json()["moved_requirement_ids"] == [requirement_id]
    assert deferred.json()["moved_task_ids"] == [task_id]
    current_detail = client.get(f"/api/v1/iterations/{iteration_id}/detail").json()
    target_detail = client.get(f"/api/v1/iterations/{target_iteration_id}/detail").json()
    assert requirement_id not in {item["id"] for item in current_detail["requirements"]}
    assert task_id not in {item["id"] for item in current_detail["tasks"]}
    assert requirement_id in {item["id"] for item in target_detail["requirements"]}
    assert task_id in {item["id"] for item in target_detail["tasks"]}

    finished = client.post(
        f"/api/v1/iterations/{iteration_id}/finish",
        json={"effective_time": "2026-06-20T18:00:00", "remark": "iteration finish"},
    )
    assert finished.status_code == 200
