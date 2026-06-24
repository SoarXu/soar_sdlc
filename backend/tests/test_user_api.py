from fastapi.testclient import TestClient


def test_register_user_returns_token_and_user_identity(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "new_dev",
            "password": "User123456",
            "full_name": "New Developer",
            "email": "new_dev@example.com",
            "mobile": "13800000000",
            "department": "R&D",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["token_type"] == "bearer"
    assert data["access_token"]
    assert data["username"] == "new_dev"
    assert data["full_name"] == "New Developer"


def test_registered_user_can_login(client: TestClient):
    client.post(
        "/api/v1/auth/register",
        json={"username": "login_dev", "password": "User123456", "full_name": "Login User"},
    )

    response = client.post("/api/v1/auth/login", json={"username": "login_dev", "password": "User123456"})

    assert response.status_code == 200
    assert response.json()["username"] == "login_dev"
    assert response.json()["full_name"] == "Login User"


def test_register_rejects_duplicate_username(client: TestClient):
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "admin", "password": "User123456", "full_name": "Duplicate User"},
    )

    assert response.status_code == 409


def test_users_list_returns_display_names(client: TestClient):
    response = client.get("/api/v1/users")

    assert response.status_code == 200
    users = response.json()
    assert any(user["username"] == "admin" and user["full_name"] for user in users)
    assert any(user["username"] == "pm_chen" and user["full_name"] == "陈序" for user in users)


def test_seeded_non_admin_user_can_login(client: TestClient):
    response = client.post("/api/v1/auth/login", json={"username": "pm_chen", "password": "User123456"})

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]
    assert response.json()["username"] == "pm_chen"
    assert response.json()["full_name"] == "陈序"
