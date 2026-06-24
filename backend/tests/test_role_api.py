from fastapi.testclient import TestClient
from uuid import uuid4


def test_roles_list_contains_default_business_roles(client: TestClient):
    response = client.get("/api/v1/roles")

    assert response.status_code == 200
    role_keys = {role["role_key"] for role in response.json()}
    assert {"developer", "tester", "product_manager", "development_lead"}.issubset(role_keys)


def test_create_custom_role(client: TestClient):
    role_key = f"release_manager_{uuid4().hex[:8]}"
    response = client.post(
        "/api/v1/roles",
        json={"role_key": role_key, "role_name": "Release Manager", "description": "Owns releases"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["role_key"] == role_key
    assert data["role_name"] == "Release Manager"
    assert data["enabled"] is True


def test_assign_roles_to_user_and_return_roles_on_user_read(client: TestClient):
    user_response = client.post(
        "/api/v1/auth/register",
        json={"username": "role_user", "password": "User123456", "full_name": "Role User"},
    )
    user_id = user_response.json()["user_id"]
    roles = client.get("/api/v1/roles").json()
    role_ids = [role["id"] for role in roles if role["role_key"] in {"developer", "tester"}]

    response = client.put(f"/api/v1/users/{user_id}/roles", json={"role_ids": role_ids})

    assert response.status_code == 200
    assigned_keys = {role["role_key"] for role in response.json()["roles"]}
    assert assigned_keys == {"developer", "tester"}

    users = client.get("/api/v1/users").json()
    role_user = next(user for user in users if user["username"] == "role_user")
    assert {role["role_key"] for role in role_user["roles"]} == {"developer", "tester"}
