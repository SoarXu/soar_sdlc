from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import SessionLocal


DEMO_USERNAMES = ["admin", "pm_chen", "rd_lin", "qa_wang", "po_li"]


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
    client.post(
        "/api/v1/auth/register",
        json={"username": "duplicate_user", "password": "User123456", "full_name": "Original User"},
    )

    response = client.post(
        "/api/v1/auth/register",
        json={"username": "duplicate_user", "password": "User123456", "full_name": "Duplicate User"},
    )

    assert response.status_code == 409


def test_users_list_does_not_recreate_deleted_demo_users(client: TestClient):
    _delete_users_by_username(DEMO_USERNAMES)

    response = client.get("/api/v1/users")

    assert response.status_code == 200
    users = response.json()
    usernames = {user["username"] for user in users}
    assert usernames.isdisjoint(DEMO_USERNAMES)


def _delete_users_by_username(usernames: list[str]) -> None:
    db = SessionLocal()
    try:
        user_ids = [
            row.id
            for row in db.execute(
                text("select id from users where username in :usernames"),
                {"usernames": tuple(usernames)},
            ).all()
        ]
        if user_ids:
            db.execute(text("delete from user_roles where user_id in :ids"), {"ids": tuple(user_ids)})
            db.execute(text("delete from users where id in :ids"), {"ids": tuple(user_ids)})
        db.commit()
    finally:
        db.close()
