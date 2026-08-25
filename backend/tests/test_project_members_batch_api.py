from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.db.session import SessionLocal
from app.models.project_member import ProjectMember
from app.models.role import Role
from app.models.user import User


def test_project_members_batch_groups_members_and_enforces_visibility(client: TestClient):
    first = client.post("/api/v1/projects", json={"name": f"Batch Members A {uuid4().hex[:8]}"}).json()
    second = client.post("/api/v1/projects", json={"name": f"Batch Members B {uuid4().hex[:8]}"}).json()
    db = SessionLocal()
    try:
        role = db.query(Role).filter(Role.enabled.is_(True)).first()
        member = User(
            username=f"batch_member_{uuid4().hex[:8]}",
            full_name="Batch Project Member",
            password_hash=get_password_hash("User123456"),
            is_active=True,
        )
        outsider = User(
            username=f"batch_outsider_{uuid4().hex[:8]}",
            full_name="Batch Project Outsider",
            password_hash=get_password_hash("User123456"),
            is_active=True,
        )
        db.add_all([member, outsider])
        db.flush()
        db.add(ProjectMember(project_id=first["id"], user_id=member.id, role_id=role.id))
        db.commit()
        member_id = member.id
        outsider_token = create_access_token(outsider.username)
    finally:
        db.close()

    response = client.post(
        "/api/v1/projects/members/batch",
        json={"project_ids": [first["id"], second["id"]]},
    )
    rejected = client.post(
        "/api/v1/projects/members/batch",
        json={"project_ids": [first["id"]]},
        headers={"Authorization": f"Bearer {outsider_token}"},
    )

    assert response.status_code == 200, response.text
    members_by_project = {item["project_id"]: item["members"] for item in response.json()["items"]}
    assert [item["user_id"] for item in members_by_project[first["id"]]] == [member_id]
    assert members_by_project[second["id"]] == []
    assert rejected.status_code == 403


def test_project_members_batch_accepts_empty_project_list(client: TestClient):
    response = client.post("/api/v1/projects/members/batch", json={"project_ids": []})

    assert response.status_code == 200
    assert response.json() == {"items": []}
