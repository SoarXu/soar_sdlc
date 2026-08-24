from uuid import uuid4

from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.models.task import Task
from app.services import task_hierarchy_service


def _create_task(client: TestClient, project_id: int, title: str) -> dict:
    response = client.post(
        "/api/v1/tasks",
        json={"project_id": project_id, "title": title},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _set_parent(child_id: int, parent_id: int) -> None:
    with SessionLocal() as db:
        db.query(Task).filter(Task.id == child_id).update({Task.parent_task_id: parent_id})
        db.commit()


def test_task_tree_traversal_returns_direct_children_and_all_active_descendants_in_depth_order(client: TestClient):
    project = client.post("/api/v1/projects", json={"name": f"Task hierarchy {uuid4().hex[:8]}"}).json()
    root = _create_task(client, project["id"], "root")
    first_child = _create_task(client, project["id"], "first child")
    second_child = _create_task(client, project["id"], "second child")
    grandchild = _create_task(client, project["id"], "grandchild")
    deleted_child = _create_task(client, project["id"], "deleted child")
    _set_parent(first_child["id"], root["id"])
    _set_parent(second_child["id"], root["id"])
    _set_parent(grandchild["id"], first_child["id"])
    _set_parent(deleted_child["id"], root["id"])
    with SessionLocal() as db:
        db.query(Task).filter(Task.id == deleted_child["id"]).update({Task.deleted: 1})
        db.commit()
        loaded_root = db.query(Task).filter(Task.id == root["id"]).one()

        direct_children = task_hierarchy_service.list_direct_children(db, loaded_root.id)
        descendants = task_hierarchy_service.list_descendants(db, loaded_root.id)
        tree = task_hierarchy_service.task_tree(db, loaded_root)

    assert [task.id for task in direct_children] == [first_child["id"], second_child["id"]]
    assert [task.id for task in descendants] == [first_child["id"], second_child["id"], grandchild["id"]]
    assert [task.id for task in tree] == [root["id"], first_child["id"], second_child["id"], grandchild["id"]]
