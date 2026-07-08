from fastapi.testclient import TestClient
from sqlalchemy import text
from uuid import uuid4

from app.db.session import SessionLocal
from app.services.role_service import seed_default_roles
from app.services.user_service import seed_default_users


DEMO_USERNAMES = ["admin", "pm_chen", "rd_lin", "qa_wang", "po_li"]


def test_public_registration_route_is_not_available(client: TestClient):
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

    assert response.status_code == 404


def test_admin_created_user_can_login_after_password_change(client: TestClient):
    admin_token = _admin_token(client)
    create_response = client.post(
        "/api/v1/users",
        json={"username": "login_dev", "full_name": "Login User", "role_ids": []},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    initial_password = create_response.json()["initial_password"]
    first_login = client.post("/api/v1/auth/login", json={"username": "login_dev", "password": initial_password})
    token = first_login.json()["access_token"]
    client.post(
        "/api/v1/auth/change-password",
        json={"current_password": initial_password, "new_password": "User123456!"},
        headers={"Authorization": f"Bearer {token}"},
    )

    response = client.post("/api/v1/auth/login", json={"username": "login_dev", "password": "User123456!"})

    assert response.status_code == 200
    assert response.json()["username"] == "login_dev"
    assert response.json()["full_name"] == "Login User"
    assert response.json()["must_change_password"] is False


def test_users_list_does_not_recreate_deleted_demo_users(client: TestClient):
    _delete_users_by_username(DEMO_USERNAMES)

    response = client.get("/api/v1/users")

    assert response.status_code == 200
    users = response.json()
    usernames = {user["username"] for user in users}
    assert usernames.isdisjoint(DEMO_USERNAMES)


def test_admin_can_create_user_with_one_time_password_and_user_must_change_it(client: TestClient):
    admin_token = _admin_token(client)
    username = f"managed_{uuid4().hex[:8]}"

    response = client.post(
        "/api/v1/users",
        json={
            "username": username,
            "full_name": "Managed User",
            "email": "managed@example.com",
            "mobile": "13900000000",
            "department": "QA",
            "role_ids": _role_ids(client, {"developer"}),
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["user"]["username"] == username
    assert data["user"]["must_change_password"] is True
    assert len(data["initial_password"]) >= 14

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": data["initial_password"]},
    )

    assert login_response.status_code == 200
    assert login_response.json()["must_change_password"] is True


def test_user_can_change_initial_password_and_clear_required_flag(client: TestClient):
    admin_token = _admin_token(client)
    username = f"change_pwd_{uuid4().hex[:8]}"
    create_response = client.post(
        "/api/v1/users",
        json={"username": username, "full_name": "Change Password User", "role_ids": []},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    initial_password = create_response.json()["initial_password"]
    user_token = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": initial_password},
    ).json()["access_token"]

    response = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": initial_password, "new_password": "NewPassword123!"},
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 204
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "NewPassword123!"},
    )
    assert login_response.status_code == 200
    assert login_response.json()["must_change_password"] is False


def test_admin_can_reset_password_and_force_password_change_again(client: TestClient):
    admin_token = _admin_token(client)
    username = f"reset_pwd_{uuid4().hex[:8]}"
    create_response = client.post(
        "/api/v1/users",
        json={"username": username, "full_name": "Reset Password User", "role_ids": []},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    user_id = create_response.json()["user"]["id"]
    initial_password = create_response.json()["initial_password"]
    user_token = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": initial_password},
    ).json()["access_token"]
    client.post(
        "/api/v1/auth/change-password",
        json={"current_password": initial_password, "new_password": "ChangedPassword123!"},
        headers={"Authorization": f"Bearer {user_token}"},
    )

    response = client.post(
        f"/api/v1/users/{user_id}/reset-password",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    reset_password = response.json()["initial_password"]
    assert reset_password
    assert reset_password != initial_password
    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": reset_password},
    )
    assert login_response.status_code == 200
    assert login_response.json()["must_change_password"] is True


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


def _admin_token(client: TestClient) -> str:
    _ensure_admin()
    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert response.status_code == 200
    return response.json()["access_token"]


def _role_ids(client: TestClient, role_keys: set[str]) -> list[int]:
    roles = client.get("/api/v1/roles").json()
    return [role["id"] for role in roles if role["role_key"] in role_keys]


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
