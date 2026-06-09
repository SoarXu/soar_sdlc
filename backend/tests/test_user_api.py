from fastapi.testclient import TestClient


def test_users_list_returns_display_names(client: TestClient):
    response = client.get("/api/v1/users")

    assert response.status_code == 200
    users = response.json()
    assert any(user["username"] == "admin" and user["full_name"] for user in users)
