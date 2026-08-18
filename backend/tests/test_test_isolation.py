from sqlalchemy import text

from app.db.session import SessionLocal
from app.models.user import User
from tests.conftest import (
    TEST_USER_ALLOWLIST,
    _cleanup_created_rows,
    _deactivate_non_allowlisted_users,
    _snapshot_table_ids,
)


def test_cleanup_created_rows_removes_project_created_after_snapshot(client):
    before = _snapshot_table_ids()
    response = client.post("/api/v1/projects", json={"name": "cleanup-fixture-project"})
    assert response.status_code == 200
    project_id = response.json()["id"]

    _cleanup_created_rows(before)

    db = SessionLocal()
    try:
        count = db.execute(text("select count(*) from projects where id = :id"), {"id": project_id}).scalar_one()
        assert count == 0
    finally:
        db.close()


def test_test_user_cleanup_keeps_only_allowlisted_active_users(client):
    _deactivate_non_allowlisted_users()

    db = SessionLocal()
    try:
        active_usernames = {
            username
            for username, in db.query(User.username)
            .filter(User.deleted == 0, User.is_active.is_(True))
            .all()
        }
    finally:
        db.close()

    assert active_usernames == TEST_USER_ALLOWLIST

    response = client.get("/api/v1/users")

    assert response.status_code == 200
    assert {user["username"] for user in response.json()} == TEST_USER_ALLOWLIST
