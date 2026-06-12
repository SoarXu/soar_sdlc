from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text

from app.db.session import SessionLocal
from app.main import app


@pytest.fixture()
def client() -> TestClient:
    before = _snapshot_table_ids()
    try:
        yield TestClient(app)
    finally:
        _cleanup_created_rows(before)


TRACKED_TABLES = [
    "status_operation_log",
    "iteration_projects",
    "test_case_execution_log",
    "test_run_cases",
    "notification_delivery_log",
    "external_integration_mapping",
    "audit_log",
    "object_relation",
    "object_tags",
    "attachments",
    "custom_field_value",
    "form_layout_config",
    "workflow_component_registry",
    "workflow_rules",
    "notifications",
    "bugs",
    "test_runs",
    "test_cases",
    "tasks",
    "requirements",
    "iterations",
    "project_members",
    "projects",
    "programs",
    "user_roles",
    "users",
]


def _snapshot_table_ids() -> dict[str, set[int]]:
    db = SessionLocal()
    try:
        return {
            table: {row.id for row in db.execute(text(f"select id from {table}")).all()}
            for table in TRACKED_TABLES
            if _table_exists(db, table)
        }
    finally:
        db.close()


def _cleanup_created_rows(before: dict[str, set[int]]) -> None:
    db = SessionLocal()
    try:
        for table in TRACKED_TABLES:
            if table not in before or not _table_exists(db, table):
                continue
            rows = db.execute(text(f"select id from {table}")).all()
            created_ids = [row.id for row in rows if row.id not in before[table]]
            if created_ids:
                db.execute(text(f"delete from {table} where id in :ids"), {"ids": tuple(created_ids)})
        db.commit()
    finally:
        db.close()


def _table_exists(db, table: str) -> bool:
    return bool(db.execute(text("show tables like :table"), {"table": table}).first())
