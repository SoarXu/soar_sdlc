from fastapi.testclient import TestClient
from uuid import uuid4

from app.db.session import SessionLocal
from app.models.role import Role
from app.services.role_service import seed_default_roles
from app.services.user_service import seed_default_users
from sqlalchemy import text


TEMPORARY_ROLE_PREFIX = f"temporary_role_{uuid4().hex[:8]}"


def test_roles_list_contains_default_business_roles(client: TestClient):
    response = client.get("/api/v1/roles")

    assert response.status_code == 200
    role_keys = {role["role_key"] for role in response.json()}
    assert {"developer", "tester", "product_manager", "development_lead", "department_head"}.issubset(role_keys)


def test_create_custom_role(client: TestClient):
    token = _admin_token(client)
    role_key = f"release_manager_{uuid4().hex[:8]}"
    response = client.post(
        "/api/v1/roles",
        json={"role_key": role_key, "role_name": "Release Manager", "description": "Owns releases"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["role_key"] == role_key
    assert data["role_name"] == "Release Manager"
    assert data["enabled"] is True


def test_custom_roles_created_by_tests_are_isolated(client: TestClient):
    token = _admin_token(client)
    role_key = f"{TEMPORARY_ROLE_PREFIX}_created"
    response = client.post(
        "/api/v1/roles",
        json={"role_key": role_key, "role_name": "Temporary Role", "description": "Temporary test role"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201


def test_custom_role_from_previous_test_is_cleaned_up():
    db = SessionLocal()
    try:
        assert db.query(Role).filter(Role.role_key.like(f"{TEMPORARY_ROLE_PREFIX}%")).count() == 0
    finally:
        db.close()


def test_assign_roles_to_user_and_return_roles_on_user_read(client: TestClient):
    token = _admin_token(client)
    user_response = client.post(
        "/api/v1/users",
        json={"username": "role_user", "full_name": "Role User", "role_ids": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    user_id = user_response.json()["user"]["id"]
    roles = client.get("/api/v1/roles").json()
    role_ids = [role["id"] for role in roles if role["role_key"] in {"developer", "tester"}]

    response = client.put(
        f"/api/v1/users/{user_id}/roles",
        json={"role_ids": role_ids},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assigned_keys = {role["role_key"] for role in response.json()["roles"]}
    assert assigned_keys == {"developer", "tester"}

    users = client.get("/api/v1/users").json()
    role_user = next(user for user in users if user["username"] == "role_user")
    assert {role["role_key"] for role in role_user["roles"]} == {"developer", "tester"}


def test_non_admin_cannot_create_role(client: TestClient):
    admin_token = _admin_token(client)
    user_response = client.post(
        "/api/v1/users",
        json={"username": f"non_admin_{uuid4().hex[:8]}", "full_name": "Non Admin", "role_ids": []},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    initial_password = user_response.json()["initial_password"]
    username = user_response.json()["user"]["username"]
    token = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": initial_password},
    ).json()["access_token"]

    response = client.post(
        "/api/v1/roles",
        json={
            "role_key": f"blocked_role_{uuid4().hex[:8]}",
            "role_name": "Blocked Role",
            "description": "Should not be created",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


def _admin_token(client: TestClient) -> str:
    _ensure_admin()
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert response.status_code == 200
    return response.json()["access_token"]


def _ensure_admin() -> None:
    db = SessionLocal()
    try:
        seed_default_roles(db)
        seed_default_users(db)
        admin_user_id = db.execute(text("select id from users where username='admin'")).scalar()
        admin_role_id = db.execute(text("select id from roles where role_key='system_admin'")).scalar()
        if admin_user_id and admin_role_id:
            existing = db.execute(
                text("select id from user_roles where user_id=:user_id and role_id=:role_id"),
                {"user_id": admin_user_id, "role_id": admin_role_id},
            ).scalar()
            if not existing:
                db.execute(
                    text("insert into user_roles (user_id, role_id) values (:user_id, :role_id)"),
                    {"user_id": admin_user_id, "role_id": admin_role_id},
                )
                db.commit()
    finally:
        db.close()
