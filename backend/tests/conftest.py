from fastapi.testclient import TestClient
import pytest
from sqlalchemy import text

from app.core.security import create_access_token, get_password_hash
from app.db.session import SessionLocal
from app.main import app
from app.models.role import Role, UserRole
from app.models.user import User


class AuthenticatedTestClient(TestClient):
    def __init__(self, *args, default_token: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_token = default_token

    def request(self, method: str, url, **kwargs):
        headers = dict(kwargs.pop("headers", {}) or {})
        skip_default_auth = headers.pop("X-Test-No-Auth", None)
        if not skip_default_auth and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {self.default_token}"
        kwargs["headers"] = headers
        return super().request(method, url, **kwargs)


@pytest.fixture()
def client() -> TestClient:
    before = _snapshot_table_ids()
    default_token = _create_default_admin_token()
    try:
        yield AuthenticatedTestClient(app, default_token=default_token)
    finally:
        _cleanup_created_rows(before)


TRACKED_TABLES = [
    "exception_rules",
    "bug_types",
    "devops_code_review_tasks",
    "devops_commit_links",
    "devops_commits",
    "devops_jenkins_builds",
    "devops_jenkins_jobs",
    "devops_repositories",
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
    "work_item_comments",
    "object_watch",
    "notifications",
    "bugs",
    "test_runs",
    "test_cases",
    "tasks",
    "requirements",
    "workflow_transitions",
    "workflow_states",
    "workflow_definitions",
    "iterations",
    "project_members",
    "projects",
    "handler_transition_rules",
    "assignee_rule_configs",
    "programs",
    "user_roles",
    "users",
    "roles",
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
        created_state_ids = _created_ids(db, before, "workflow_states")
        if created_state_ids:
            db.execute(
                text("update workflow_definitions set initial_state_id = null where initial_state_id in :ids"),
                {"ids": tuple(created_state_ids)},
            )
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


def _created_ids(db, before: dict[str, set[int]], table: str) -> list[int]:
    if table not in before or not _table_exists(db, table):
        return []
    return [row.id for row in db.execute(text(f"select id from {table}")).all() if row.id not in before[table]]


def _table_exists(db, table: str) -> bool:
    return bool(db.execute(text("show tables like :table"), {"table": table}).first())


def _create_default_admin_token() -> str:
    db = SessionLocal()
    try:
        username = "pytest_default_admin"
        user = db.query(User).filter(User.username == username).first()
        if not user:
            user = User(
                username=username,
                full_name="Pytest Default Admin",
                password_hash=get_password_hash("User123456"),
                is_active=True,
            )
            db.add(user)
            db.flush()
        role = db.query(Role).filter(Role.role_key == "system_admin").first()
        if not role:
            role = Role(role_key="system_admin", role_name="system_admin", enabled=True, is_system=True)
            db.add(role)
            db.flush()
        exists = db.query(UserRole).filter(UserRole.user_id == user.id, UserRole.role_id == role.id).first()
        if not exists:
            db.add(UserRole(user_id=user.id, role_id=role.id))
        db.commit()
        return create_access_token(user.username)
    finally:
        db.close()
