from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.models.iteration import Iteration, IterationProject
from app.models.project import Project
from app.models.workflow_definition import WorkflowDefinition
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
