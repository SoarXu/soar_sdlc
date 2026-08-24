from datetime import datetime, timedelta
from uuid import uuid4

from app.core.security import create_access_token, get_password_hash
from app.db.session import SessionLocal
from app.models.project_member import ProjectMember
from app.models.role import Role
from app.models.task import Task
from app.models.user import User


def _create_active_workbench_tasks(client, count: int = 120):
    db = SessionLocal()
    try:
        user = User(
            username=f"workbench.page.{uuid4().hex[:8]}",
            full_name="分页工作台用户",
            password_hash=get_password_hash("User123456"),
            is_active=True,
        )
        db.add(user)
        db.flush()
        user_id = user.id
        db.commit()
        token = create_access_token(user.username)
    finally:
        db.close()
    project = client.post("/api/v1/projects", json={"name": f"分页工作台项目-{uuid4().hex[:8]}"})
    assert project.status_code == 200, project.text
    project_id = project.json()["id"]
    with SessionLocal() as db:
        role_id = db.query(Role.id).order_by(Role.id.asc()).limit(1).scalar()
        assert role_id is not None
        db.add(ProjectMember(project_id=project_id, user_id=user_id, role_id=role_id, is_workbench_participant=True))
        db.commit()
    iteration = client.post(
        "/api/v1/iterations",
        json={"name": f"分页工作台迭代-{uuid4().hex[:8]}", "project_ids": [project_id]},
    )
    assert iteration.status_code == 200, iteration.text
    started = client.post(
        f"/api/v1/workflow-runtime/iteration/{iteration.json()['id']}/transition",
        json={"action_key": "start"},
    )
    assert started.status_code == 200, started.text
    template = client.post(
        "/api/v1/tasks",
        json={
            "project_id": project_id,
            "iteration_id": iteration.json()["id"],
            "title": "分页任务 000",
            "priority": "high",
            "due_date": (datetime.now().date() - timedelta(days=1)).isoformat(),
        },
    )
    assert template.status_code == 200, template.text
    template = template.json()
    with SessionLocal() as db:
        db.add_all(
            [
                Task(
                    project_id=project_id,
                    iteration_id=iteration.json()["id"],
                    title=f"分页任务 {index:03d}",
                    task_type="standalone_operation",
                    priority="high",
                    workflow_definition_id=template["workflow_definition_id"],
                    current_state_id=template["current_state_id"],
                    creator_id=template["creator_id"],
                    due_date=datetime.now().date() - timedelta(days=1),
                )
                for index in range(1, count)
            ]
        )
        db.commit()
    return project_id, iteration.json()["id"], token


def test_workbench_items_endpoint_returns_a_bounded_stable_page_and_complete_facets(client):
    project_id, iteration_id, token = _create_active_workbench_tasks(client)

    first = client.get(
        "/api/v1/dashboard/workbench/items",
        params={"page": 1, "page_size": 20, "object_types": "task"},
        headers={"Authorization": f"Bearer {token}"},
    )
    second = client.get(
        "/api/v1/dashboard/workbench/items",
        params={"page": 2, "page_size": 20, "object_types": "task"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    first_data = first.json()
    second_data = second.json()
    assert first_data["total"] == 120
    assert first_data["page"] == 1
    assert first_data["page_size"] == 20
    assert first_data["page_count"] == 6
    assert len(first_data["items"]) == 20
    assert len(second_data["items"]) == 20
    assert not {
        (item["object_type"], item["id"])
        for item in first_data["items"]
    }.intersection({(item["object_type"], item["id"]) for item in second_data["items"]})
    assert first_data["filter_options"]["projects"] == [{"value": project_id, "label": first_data["items"][0]["project_name"]}]
    assert first_data["filter_options"]["iterations"] == [{"value": iteration_id, "label": first_data["items"][0]["iteration_name"]}]

    exact = client.get(
        "/api/v1/dashboard/workbench/items",
        params={
            "page": 1,
            "page_size": 20,
            "keyword": "分页任务 000",
            "project_ids": project_id,
            "iteration_ids": iteration_id,
            "object_types": "task",
            "state_ids": first_data["items"][0]["current_state_id"],
            "priorities": "high",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    no_handler_match = client.get(
        "/api/v1/dashboard/workbench/items",
        params={"page": 1, "page_size": 20, "handler_ids": 999999999},
        headers={"Authorization": f"Bearer {token}"},
    )
    invalid_page_size = client.get(
        "/api/v1/dashboard/workbench/items",
        params={"page": 1, "page_size": 101},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert exact.status_code == 200, exact.text
    assert exact.json()["total"] == 1
    assert exact.json()["items"][0]["title"] == "分页任务 000"
    assert no_handler_match.status_code == 200, no_handler_match.text
    assert no_handler_match.json()["total"] == 0
    assert no_handler_match.json()["filter_options"]["projects"] == first_data["filter_options"]["projects"]
    assert invalid_page_size.status_code == 422


def test_legacy_workbench_endpoint_remains_compatible(client):
    _, _, token = _create_active_workbench_tasks(client, count=1)

    response = client.get(
        "/api/v1/dashboard/workbench",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    assert "active_iteration_items" in response.json()


def test_workbench_items_and_facets_exclude_projects_outside_member_scope(client):
    visible_project_id, _, token = _create_active_workbench_tasks(client)
    hidden_project = client.post("/api/v1/projects", json={"name": f"Hidden workbench project {uuid4().hex[:8]}"})
    assert hidden_project.status_code == 200, hidden_project.text
    hidden_project_id = hidden_project.json()["id"]
    hidden_iteration = client.post(
        "/api/v1/iterations",
        json={"name": f"Hidden workbench iteration {uuid4().hex[:8]}", "project_ids": [hidden_project_id]},
    )
    assert hidden_iteration.status_code == 200, hidden_iteration.text
    hidden_iteration_id = hidden_iteration.json()["id"]
    started = client.post(
        f"/api/v1/workflow-runtime/iteration/{hidden_iteration_id}/transition",
        json={"action_key": "start"},
    )
    assert started.status_code == 200, started.text
    hidden_task = client.post(
        "/api/v1/tasks",
        json={
            "project_id": hidden_project_id,
            "iteration_id": hidden_iteration_id,
            "title": "Hidden workbench task",
        },
    )
    assert hidden_task.status_code == 200, hidden_task.text

    response = client.get(
        "/api/v1/dashboard/workbench/items",
        params={"page": 1, "page_size": 100},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 120
    assert {item["project_id"] for item in data["items"]} == {visible_project_id}
    assert {option["value"] for option in data["filter_options"]["projects"]} == {visible_project_id}
