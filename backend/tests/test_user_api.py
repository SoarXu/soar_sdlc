from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text
from uuid import uuid4

from app.core.security import create_access_token
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


def test_admin_can_create_and_edit_user_employee_number(client: TestClient):
    username = f"employee_{uuid4().hex[:8]}"
    created = client.post(
        "/api/v1/users",
        json={
            "username": username,
            "full_name": "Employee Before",
            "employee_no": "  E-1001  ",
        },
    )

    assert created.status_code == 201
    assert created.json()["user"]["employee_no"] == "E-1001"
    assert created.json()["user"]["auth_source"] == "local"

    user_id = created.json()["user"]["id"]
    updated = client.patch(
        f"/api/v1/users/{user_id}",
        json={
            "full_name": "Employee After",
            "employee_no": "  ",
            "email": "employee@example.com",
            "mobile": "13800000000",
            "department": "R&D",
        },
    )

    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Employee After"
    assert updated.json()["employee_no"] is None
    assert updated.json()["email"] == "employee@example.com"
    assert updated.json()["department"] == "R&D"


def test_duplicate_employee_number_returns_stable_conflict(client: TestClient):
    suffix = uuid4().hex[:8]
    first = client.post(
        "/api/v1/users",
        json={"username": f"first_{suffix}", "full_name": "First Employee", "employee_no": f"E-{suffix}"},
    )
    second = client.post(
        "/api/v1/users",
        json={"username": f"second_{suffix}", "full_name": "Second Employee"},
    )

    response = client.patch(
        f"/api/v1/users/{second.json()['user']['id']}",
        json={"employee_no": f"  E-{suffix}  "},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "EMPLOYEE_NO_ALREADY_EXISTS",
        "message": "工号已被其他用户使用",
    }


def test_non_admin_cannot_edit_user_profile(client: TestClient):
    target = next(user for user in client.get("/api/v1/users").json() if user["username"] == "bob")

    response = client.patch(
        f"/api/v1/users/{target['id']}",
        json={"employee_no": "E-NOT-ALLOWED"},
        headers={"Authorization": f"Bearer {create_access_token('bob')}"},
    )

    assert response.status_code == 403


def test_admin_cannot_choose_auth_source_when_creating_user(client: TestClient):
    response = client.post(
        "/api/v1/users",
        json={
            "username": f"forged_ldap_{uuid4().hex[:8]}",
            "full_name": "Forged LDAP User",
            "auth_source": "ldap",
        },
    )

    assert response.status_code == 422


def test_duplicate_employee_number_on_create_returns_stable_conflict(client: TestClient):
    suffix = uuid4().hex[:8]
    employee_no = f"E-{suffix}"
    first = client.post(
        "/api/v1/users",
        json={"username": f"create_first_{suffix}", "full_name": "First Employee", "employee_no": employee_no},
    )

    response = client.post(
        "/api/v1/users",
        json={"username": f"create_second_{suffix}", "full_name": "Second Employee", "employee_no": employee_no},
    )

    assert first.status_code == 201
    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "EMPLOYEE_NO_ALREADY_EXISTS",
        "message": "工号已被其他用户使用",
    }


@pytest.mark.parametrize(
    ("state_update", "state_name"),
    [({"is_active": 0}, "inactive"), ({"deleted": 1}, "deleted")],
)
def test_employee_number_can_be_reused_after_user_becomes_invalid(
    client: TestClient,
    state_update: dict[str, int],
    state_name: str,
):
    suffix = uuid4().hex[:8]
    employee_no = f"E-{suffix}"
    first = client.post(
        "/api/v1/users",
        json={"username": f"old_{state_name}_{suffix}", "full_name": "Former Employee", "employee_no": employee_no},
    )
    user_id = first.json()["user"]["id"]
    assignment = ", ".join(f"{column}=:{column}" for column in state_update)
    db = SessionLocal()
    try:
        db.execute(text(f"update users set {assignment} where id=:user_id"), {**state_update, "user_id": user_id})
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/api/v1/users",
        json={"username": f"new_{state_name}_{suffix}", "full_name": "Replacement Employee", "employee_no": employee_no},
    )

    assert response.status_code == 201
    assert response.json()["user"]["employee_no"] == employee_no


def test_employee_number_longer_than_64_characters_is_rejected(client: TestClient):
    response = client.post(
        "/api/v1/users",
        json={
            "username": f"long_employee_{uuid4().hex[:8]}",
            "full_name": "Long Employee Number",
            "employee_no": "E" * 65,
        },
    )

    assert response.status_code == 422


def test_users_list_requires_authentication(client: TestClient):
    response = client.get("/api/v1/users", headers={"X-Test-No-Auth": "1"})

    assert response.status_code == 401


def test_authenticated_non_admin_can_list_users(client: TestClient):
    response = client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {create_access_token('bob')}"},
    )

    assert response.status_code == 200


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
