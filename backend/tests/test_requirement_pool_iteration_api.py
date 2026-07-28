from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.models.iteration import Iteration, IterationProject
from app.models.project import Project
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
