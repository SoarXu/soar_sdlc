from fastapi.testclient import TestClient


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
