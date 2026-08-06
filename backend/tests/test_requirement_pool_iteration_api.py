from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.bug import Bug
from app.models.iteration import Iteration, IterationProject
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.requirement import Requirement
from app.models.task import Task
from app.models.workflow_definition import WorkflowDefinition, WorkflowState, WorkflowTransition
from app.services import project_service
from app.services.requirement_pool_service import requirement_pool_for_project


def _create_project(client: TestClient, name_prefix: str = "Requirement pool") -> dict:
    response = client.post("/api/v1/projects", json={"name": f"{name_prefix}-{uuid4().hex[:8]}"})
    assert response.status_code == 200, response.text
    return response.json()


def test_project_creation_builds_one_canonical_requirement_pool(client: TestClient):
    project = _create_project(client)

    db = SessionLocal()
    try:
        pool = requirement_pool_for_project(db, project["id"])
        memberships = db.query(IterationProject).filter(IterationProject.iteration_id == pool.id).all()

        assert project["requirement_pool_iteration_id"] == pool.id
        assert pool.name == "需求池"
        assert pool.is_requirement_pool is True
        assert [membership.project_id for membership in memberships] == [project["id"]]
    finally:
        db.close()


def test_project_creation_rolls_back_when_pool_creation_fails(client: TestClient, monkeypatch):
    project_name = f"Atomic project-{uuid4().hex[:8]}"

    def _raise(*_args, **_kwargs):
        raise HTTPException(status_code=409, detail="pool creation failed")

    monkeypatch.setattr(project_service, "create_project_requirement_pool", _raise)

    response = client.post("/api/v1/projects", json={"name": project_name})

    assert response.status_code == 409
    db = SessionLocal()
    try:
        assert db.query(Project).filter(Project.name == project_name).count() == 0
    finally:
        db.close()


def test_project_creation_does_not_persist_when_iteration_default_workflow_is_invalid(client: TestClient):
    project_name = f"Invalid iteration workflow project-{uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        iteration_workflow = (
            db.query(WorkflowDefinition)
            .filter(
                WorkflowDefinition.object_type == "iteration",
                WorkflowDefinition.scope_type == "system",
                WorkflowDefinition.is_default_template.is_(True),
            )
            .one()
        )
        was_enabled = iteration_workflow.enabled
        iteration_workflow.enabled = False
        db.commit()

        response = client.post("/api/v1/projects", json={"name": project_name})

        assert response.status_code == 409
        assert db.query(Project).filter(Project.name == project_name).count() == 0
    finally:
        db.rollback()
        if "iteration_workflow" in locals():
            db.query(WorkflowDefinition).filter(WorkflowDefinition.id == iteration_workflow.id).update(
                {"enabled": was_enabled}
            )
            db.commit()
        db.close()


def test_user_created_iteration_is_never_a_requirement_pool(client: TestClient):
    project = _create_project(client, "Delivery project")

    response = client.post(
        "/api/v1/iterations",
        json={
            "name": f"Delivery iteration-{uuid4().hex[:8]}",
            "project_id": project["id"],
            "is_requirement_pool": True,
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["is_requirement_pool"] is False


@pytest.mark.parametrize("corruption", ["missing_reference", "wrong_flag", "missing_membership", "extra_membership"])
def test_requirement_pool_helper_rejects_corrupted_pool_identity(client: TestClient, corruption: str):
    project = _create_project(client, f"Corrupted pool {corruption}")
    db = SessionLocal()
    try:
        pool_id = project["requirement_pool_iteration_id"]
        if corruption == "missing_reference":
            db.query(Project).filter(Project.id == project["id"]).update({"requirement_pool_iteration_id": None})
        elif corruption == "wrong_flag":
            db.query(Iteration).filter(Iteration.id == pool_id).update({"is_requirement_pool": False})
        elif corruption == "missing_membership":
            db.query(IterationProject).filter(
                IterationProject.iteration_id == pool_id,
                IterationProject.project_id == project["id"],
            ).delete()
        else:
            other_project = _create_project(client, "Unrelated project")
            db.add(IterationProject(iteration_id=pool_id, project_id=other_project["id"]))
        db.commit()
        db.expire_all()

        with pytest.raises(HTTPException) as exc_info:
            requirement_pool_for_project(db, project["id"])

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["code"] == "REQUIREMENT_POOL_INTEGRITY_ERROR"
    finally:
        db.close()


def _create_delivery_iteration(client: TestClient, project_id: int, name_prefix: str = "Delivery") -> dict:
    response = client.post(
        "/api/v1/iterations",
        json={"project_ids": [project_id], "name": f"{name_prefix}-{uuid4().hex[:8]}"},
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("payload", [{}, {"iteration_id": None}])
def test_requirement_creation_without_iteration_uses_canonical_pool(client: TestClient, payload: dict):
    project = _create_project(client, "Create into pool")

    created = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "title": f"Pool requirement-{uuid4().hex[:8]}", **payload},
    )

    assert created.status_code == 200, created.text
    assert created.json()["iteration_id"] == project["requirement_pool_iteration_id"]


def test_requirement_creation_keeps_explicit_delivery_iteration(client: TestClient):
    project = _create_project(client, "Create into delivery")
    delivery = _create_delivery_iteration(client, project["id"])

    created = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project["id"],
            "iteration_id": delivery["id"],
            "title": f"Delivery requirement-{uuid4().hex[:8]}",
        },
    )

    assert created.status_code == 200, created.text
    assert created.json()["iteration_id"] == delivery["id"]


def test_direct_task_and_bug_creation_without_iteration_use_project_pool(client: TestClient):
    project = _create_project(client, "Direct work into pool")

    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "title": "Direct unplanned task"},
    )
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project["id"], "title": "Direct unplanned bug"},
    )

    assert task.status_code == 200, task.text
    assert bug.status_code == 200, bug.text
    assert task.json()["iteration_id"] == project["requirement_pool_iteration_id"]
    assert bug.json()["iteration_id"] == project["requirement_pool_iteration_id"]


def test_bug_creation_inherits_linked_requirement_delivery_iteration(client: TestClient):
    project = _create_project(client, "Bug source iteration")
    delivery = _create_delivery_iteration(client, project["id"])
    requirement = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project["id"],
            "iteration_id": delivery["id"],
            "title": "Delivery requirement with bug",
        },
    )
    assert requirement.status_code == 200, requirement.text

    bug = client.post(
        "/api/v1/bugs",
        json={
            "project_id": project["id"],
            "requirement_id": requirement.json()["id"],
            "title": "Inherited delivery bug",
        },
    )

    assert bug.status_code == 200, bug.text
    assert bug.json()["iteration_id"] == delivery["id"]


def test_clearing_task_or_bug_iteration_moves_item_back_to_project_pool(client: TestClient):
    project = _create_project(client, "Clear iteration into pool")
    delivery = _create_delivery_iteration(client, project["id"])
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "iteration_id": delivery["id"], "title": "Delivery task"},
    )
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project["id"], "iteration_id": delivery["id"], "title": "Delivery bug"},
    )
    assert task.status_code == 200, task.text
    assert bug.status_code == 200, bug.text

    cleared_task = client.patch(f"/api/v1/tasks/{task.json()['id']}", json={"iteration_id": None})
    cleared_bug = client.patch(f"/api/v1/bugs/{bug.json()['id']}", json={"iteration_id": None})

    assert cleared_task.status_code == 200, cleared_task.text
    assert cleared_bug.status_code == 200, cleared_bug.text
    assert cleared_task.json()["iteration_id"] == project["requirement_pool_iteration_id"]
    assert cleared_bug.json()["iteration_id"] == project["requirement_pool_iteration_id"]


def test_requirement_creation_rejects_foreign_or_noncanonical_pool(client: TestClient):
    project = _create_project(client, "Canonical pool")
    foreign_project = _create_project(client, "Foreign pool")
    delivery = _create_delivery_iteration(client, project["id"], "Corrupted pool")
    db = SessionLocal()
    try:
        db.query(Iteration).filter(Iteration.id == delivery["id"]).update({"is_requirement_pool": True})
        db.commit()
    finally:
        db.close()

    foreign = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project["id"],
            "iteration_id": foreign_project["requirement_pool_iteration_id"],
            "title": f"Foreign pool requirement-{uuid4().hex[:8]}",
        },
    )
    noncanonical = client.post(
        "/api/v1/requirements",
        json={
            "project_id": project["id"],
            "iteration_id": delivery["id"],
            "title": f"Noncanonical pool requirement-{uuid4().hex[:8]}",
        },
    )

    assert foreign.status_code == 400
    assert noncanonical.status_code == 400


def test_requirement_pool_allows_name_only_rename_and_records_audit(client: TestClient):
    project = _create_project(client, "Rename pool")
    pool_id = project["requirement_pool_iteration_id"]
    renamed = f"Unscheduled work-{uuid4().hex[:8]}"

    response = client.patch(f"/api/v1/iterations/{pool_id}", json={"name": renamed})

    assert response.status_code == 200, response.text
    assert response.json()["name"] == renamed
    db = SessionLocal()
    try:
        pool = db.query(Iteration).filter(Iteration.id == pool_id).one()
        audit = (
            db.query(AuditLog)
            .filter(AuditLog.object_type == "iteration", AuditLog.object_id == pool_id, AuditLog.action == "update")
            .one()
        )
        assert pool.is_requirement_pool is True
        assert project["requirement_pool_iteration_id"] == pool.id
        assert audit.before_data == {"name": "需求池"}
        assert audit.after_data == {"name": renamed}
    finally:
        db.close()


@pytest.mark.parametrize(
    "payload",
    [
        {"owner_id": 1},
        {"start_date": "2026-01-01"},
        {"end_date": "2026-01-31"},
        {"actual_start_date": "2026-01-01"},
        {"actual_end_date": "2026-01-31"},
        {"goal": "Must not be editable"},
        {"lifecycle_phase": "product"},
        {"project_ids": []},
    ],
)
def test_requirement_pool_rejects_non_name_update(client: TestClient, payload: dict):
    project = _create_project(client, "Protected pool update")

    response = client.patch(f"/api/v1/iterations/{project['requirement_pool_iteration_id']}", json=payload)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "REQUIREMENT_POOL_OPERATION_FORBIDDEN"


@pytest.mark.parametrize("name", ["", "   ", "需求池"])
def test_requirement_pool_rejects_blank_or_unchanged_name(client: TestClient, name: str):
    project = _create_project(client, "Protected pool name")

    response = client.patch(f"/api/v1/iterations/{project['requirement_pool_iteration_id']}", json={"name": name})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "REQUIREMENT_POOL_OPERATION_FORBIDDEN"


@pytest.mark.parametrize(
    "method,path_suffix,json",
    [
        ("delete", "", None),
        ("get", "/detail", None),
        ("get", "/available-requirements", None),
        ("post", "/requirements", {"requirement_ids": []}),
        ("delete", "/requirements/999999", None),
        ("get", "/available-tasks", None),
        ("post", "/tasks", {"task_ids": []}),
        ("delete", "/tasks/999999", None),
    ],
)
def test_requirement_pool_rejects_delivery_iteration_operations(client: TestClient, method: str, path_suffix: str, json: dict | None):
    project = _create_project(client, "Protected pool operations")
    pool_id = project["requirement_pool_iteration_id"]

    response = client.request(method, f"/api/v1/iterations/{pool_id}{path_suffix}", json=json)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "REQUIREMENT_POOL_OPERATION_FORBIDDEN"


def test_requirement_pool_rejects_defer_as_source_or_target(client: TestClient):
    project = _create_project(client, "Protected pool defer")
    pool_id = project["requirement_pool_iteration_id"]
    delivery = _create_delivery_iteration(client, project["id"], "Defer delivery")

    source_response = client.post(
        f"/api/v1/iterations/{pool_id}/defer-work-items",
        json={"target_iteration_id": delivery["id"]},
    )
    target_response = client.post(
        f"/api/v1/iterations/{delivery['id']}/defer-work-items",
        json={"target_iteration_id": pool_id},
    )

    for response in (source_response, target_response):
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "REQUIREMENT_POOL_OPERATION_FORBIDDEN"


def test_delivery_iteration_still_supports_ordinary_update(client: TestClient):
    project = _create_project(client, "Delivery remains mutable")
    delivery = _create_delivery_iteration(client, project["id"])

    response = client.patch(f"/api/v1/iterations/{delivery['id']}", json={"goal": "Ship the release"})

    assert response.status_code == 200, response.text
    assert response.json()["goal"] == "Ship the release"


def test_project_iteration_page_includes_canonical_pool_while_global_lists_remain_delivery_only(client: TestClient):
    project = _create_project(client, "Pool list scope")
    pool_id = project["requirement_pool_iteration_id"]
    deliveries = [
        _create_delivery_iteration(client, project["id"], f"Visible delivery {index}") for index in range(3)
    ]

    default_items = client.get("/api/v1/iterations", params={"project_id": project["id"]}).json()
    selector_items = client.get(
        "/api/v1/iterations",
        params={"project_id": project["id"], "include_requirement_pool": True},
    ).json()
    project_page = client.get(
        f"/api/v1/projects/{project['id']}/iterations",
        params={"page": 1, "page_size": 2},
    ).json()

    assert {item["id"] for item in default_items} == {delivery["id"] for delivery in deliveries}
    assert {item["id"] for item in selector_items} == {pool_id, *(delivery["id"] for delivery in deliveries)}
    assert next(item for item in selector_items if item["id"] == pool_id)["is_requirement_pool"] is True
    project_page_items = project_page["items"]

    assert [item["id"] for item in project_page_items] == [deliveries[2]["id"], deliveries[1]["id"]]
    assert project_page["total"] == len(deliveries)
    assert all(item["is_requirement_pool"] is False for item in project_page_items)
    assert project_page["requirement_pool"]["id"] == pool_id
    assert project_page["requirement_pool"]["is_requirement_pool"] is True


def test_project_iteration_page_reports_non_terminal_work_pool_counts(client: TestClient):
    project = _create_project(client, "Work pool summary")
    pool_id = project["requirement_pool_iteration_id"]
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "title": "Unplanned requirement"},
    )
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "iteration_id": pool_id, "title": "Unplanned task"},
    )
    terminal_task = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "iteration_id": pool_id, "title": "Legacy terminal pool task"},
    )
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project["id"], "iteration_id": pool_id, "title": "Unplanned bug"},
    )
    for response in (requirement, task, terminal_task, bug):
        assert response.status_code == 200, response.text

    db = SessionLocal()
    try:
        terminal_state_id = (
            db.query(WorkflowState.id)
            .filter(
                WorkflowState.definition_id == terminal_task.json()["workflow_definition_id"],
                WorkflowState.category == "terminal",
            )
            .first()
        )[0]
        db.query(Task).filter(Task.id == terminal_task.json()["id"]).update(
            {"current_state_id": terminal_state_id}
        )
        db.commit()
    finally:
        db.close()

    page = client.get(f"/api/v1/projects/{project['id']}/iterations").json()

    assert page["requirement_pool"] == {
        **{key: value for key, value in page["requirement_pool"].items() if key not in {
            "requirement_count", "task_count", "bug_count", "total_count"
        }},
        "requirement_count": 1,
        "task_count": 1,
        "bug_count": 1,
        "total_count": 3,
    }


@pytest.mark.parametrize(
    "object_type,create_path,model",
    [
        ("requirement", "/api/v1/requirements", Requirement),
        ("task", "/api/v1/tasks", Task),
        ("bug", "/api/v1/bugs", Bug),
    ],
)
def test_pool_work_item_requires_delivery_iteration_before_execution(
    client: TestClient,
    object_type: str,
    create_path: str,
    model,
):
    project = _create_project(client, f"Pool execution guard {object_type}")
    pool_id = project["requirement_pool_iteration_id"]
    delivery = _create_delivery_iteration(client, project["id"], "Execution target")
    created = client.post(
        create_path,
        json={"project_id": project["id"], "title": f"Unplanned {object_type}"},
    )
    assert created.status_code == 200, created.text
    item = created.json()

    db = SessionLocal()
    try:
        db.add(
            ProjectMember(
                project_id=project["id"],
                user_id=item["creator_id"],
                project_role="project_owner",
                is_workbench_participant=True,
            )
        )
        db.commit()
    finally:
        db.close()
    linked_task_id = None
    if object_type == "requirement":
        linked_task = client.post(
            "/api/v1/tasks",
            json={
                "project_id": project["id"],
                "requirement_id": item["id"],
                "title": "Task synchronized with requirement",
            },
        )
        assert linked_task.status_code == 200, linked_task.text
        linked_task_id = linked_task.json()["id"]

    if object_type == "bug":
        db = SessionLocal()
        try:
            db.query(Bug).filter(Bug.id == item["id"]).update({"owner_id": item["creator_id"]})
            db.commit()
        finally:
            db.close()

    actions = client.get(
        f"/api/v1/workflow-runtime/{object_type}/{item['id']}/transitions"
    )
    assert actions.status_code == 200, actions.text
    db = SessionLocal()
    try:
        execution_action = next(
            action
            for action in actions.json()
            if db.query(WorkflowState.category)
            .join(WorkflowTransition, WorkflowTransition.to_state_id == WorkflowState.id)
            .filter(
                WorkflowTransition.id == action["transition_id"],
                WorkflowState.category.in_(("normal", "terminal")),
            )
            .scalar()
            in {"normal", "terminal"}
        )
    finally:
        db.close()
    target_field = next(
        field
        for field in execution_action["form_config"]["fields"]
        if field["field"] == "target_iteration_id"
    )
    assert target_field["required"] is True
    assert {option["value"] for option in target_field["options"]} == {delivery["id"]}

    action_payload = {}
    bug_type_field = next(
        (
            field
            for field in execution_action["form_config"]["fields"]
            if field["field"] == "bug_type"
        ),
        None,
    )
    if bug_type_field:
        action_payload["bug_type"] = bug_type_field["options"][0]["value"]
    next_owner_payload = (
        {"next_owner_id": item["creator_id"]}
        if execution_action["action_key"] == "assign"
        else {}
    )

    missing_target = client.post(
        f"/api/v1/workflow-runtime/{object_type}/{item['id']}/transition",
        json={
            "transition_id": execution_action["transition_id"],
            "payload": action_payload,
            **next_owner_payload,
        },
        headers={"X-Test-Raw-Transition-Request": "1"},
    )
    assert missing_target.status_code == 422, missing_target.text
    assert missing_target.json()["detail"] == {
        "code": "TARGET_ITERATION_REQUIRED",
        "message": "请选择正式执行迭代",
    }

    pool_target = client.post(
        f"/api/v1/workflow-runtime/{object_type}/{item['id']}/transition",
        json={
            "transition_id": execution_action["transition_id"],
            "payload": {**action_payload, "target_iteration_id": pool_id},
            **next_owner_payload,
        },
        headers={"X-Test-Raw-Transition-Request": "1"},
    )
    assert pool_target.status_code == 422, pool_target.text
    assert pool_target.json()["detail"]["code"] == "INVALID_TARGET_ITERATION"

    executed = client.post(
        f"/api/v1/workflow-runtime/{object_type}/{item['id']}/transition",
        json={
            "transition_id": execution_action["transition_id"],
            "payload": {**action_payload, "target_iteration_id": delivery["id"]},
            **next_owner_payload,
        },
        headers={"X-Test-Raw-Transition-Request": "1"},
    )
    assert executed.status_code == 200, executed.text

    db = SessionLocal()
    try:
        assert db.query(model.iteration_id).filter(model.id == item["id"]).scalar() == delivery["id"]
        if linked_task_id:
            assert db.query(Task.iteration_id).filter(Task.id == linked_task_id).scalar() == delivery["id"]
    finally:
        db.close()


def test_project_pool_filter_and_iteration_link_support_tasks_and_bugs(client: TestClient):
    project = _create_project(client, "Plan task and bug")
    pool_id = project["requirement_pool_iteration_id"]
    delivery = _create_delivery_iteration(client, project["id"], "Planned delivery")
    task = client.post(
        "/api/v1/tasks",
        json={"project_id": project["id"], "title": "Pool task to plan"},
    )
    delivery_task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project["id"],
            "iteration_id": delivery["id"],
            "title": "Already planned task",
        },
    )
    bug = client.post(
        "/api/v1/bugs",
        json={"project_id": project["id"], "title": "Pool bug to plan"},
    )
    assert task.status_code == 200, task.text
    assert delivery_task.status_code == 200, delivery_task.text
    assert bug.status_code == 200, bug.text

    task_page = client.get(
        f"/api/v1/projects/{project['id']}/tasks",
        params={"iteration_id": pool_id},
    )
    assert task_page.status_code == 200, task_page.text
    assert [item["id"] for item in task_page.json()["items"]] == [task.json()["id"]]

    linked_tasks = client.post(
        f"/api/v1/iterations/{delivery['id']}/tasks",
        json={"task_ids": [task.json()["id"]]},
    )
    linked_bugs = client.post(
        f"/api/v1/iterations/{delivery['id']}/bugs",
        json={"bug_ids": [bug.json()["id"]]},
    )
    assert linked_tasks.status_code == 200, linked_tasks.text
    assert linked_bugs.status_code == 200, linked_bugs.text
    assert client.get(f"/api/v1/tasks/{task.json()['id']}").json()["iteration_id"] == delivery["id"]
    assert client.get(f"/api/v1/bugs/{bug.json()['id']}").json()["iteration_id"] == delivery["id"]


def test_failed_pool_transition_rolls_back_item_and_linked_task_migration(client: TestClient):
    project = _create_project(client, "Atomic pool transition")
    pool_id = project["requirement_pool_iteration_id"]
    delivery = _create_delivery_iteration(client, project["id"], "Rejected execution target")
    requirement = client.post(
        "/api/v1/requirements",
        json={"project_id": project["id"], "title": "Requirement blocked by open task"},
    )
    assert requirement.status_code == 200, requirement.text
    task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project["id"],
            "requirement_id": requirement.json()["id"],
            "title": "Open task blocks terminal transition",
        },
    )
    assert task.status_code == 200, task.text

    canceled = client.post(
        f"/api/v1/workflow-runtime/requirement/{requirement.json()['id']}/transition",
        json={
            "action_key": "cancel",
            "payload": {"target_iteration_id": delivery["id"]},
        },
    )

    assert canceled.status_code == 400, canceled.text
    assert client.get(f"/api/v1/requirements/{requirement.json()['id']}").json()["iteration_id"] == pool_id
    assert client.get(f"/api/v1/tasks/{task.json()['id']}").json()["iteration_id"] == pool_id
