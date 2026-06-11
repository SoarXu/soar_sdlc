from sqlalchemy import text

from app.db.session import SessionLocal
from tests.conftest import _cleanup_created_rows, _snapshot_table_ids


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
