from fastapi.testclient import TestClient
import json
import pytest
import re
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
        skip_transition_adapter = headers.pop("X-Test-Raw-Transition-Request", None)
        legacy_graph_keys = []
        if not skip_transition_adapter:
            kwargs = _adapt_legacy_transition_request(method, str(url), kwargs)
            kwargs, legacy_graph_keys = _adapt_legacy_graph_request(method, str(url), kwargs)
        if not skip_default_auth and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {self.default_token}"
        kwargs["headers"] = headers
        response = super().request(method, url, **kwargs)
        if not skip_transition_adapter:
            _restore_legacy_graph_keys(response, legacy_graph_keys)
            _adapt_legacy_transition_response(method, str(url), response)
        return response


def _adapt_legacy_transition_request(method: str, url: str, kwargs: dict) -> dict:
    match = re.search(r"/workflow-runtime/(requirement|task|bug|iteration|project)/(\d+)/transition$", url)
    payload = kwargs.get("json")
    if method.upper() != "POST" or not match or not isinstance(payload, dict) or "action_key" not in payload:
        return kwargs
    table_by_type = {
        "requirement": "requirements",
        "task": "tasks",
        "bug": "bugs",
        "iteration": "iterations",
        "project": "projects",
    }
    object_type, object_id = match.groups()
    db = SessionLocal()
    try:
        transition_id = db.execute(
            text(
                f"SELECT transition_row.id FROM workflow_transitions transition_row "
                f"JOIN {table_by_type[object_type]} item "
                "ON item.workflow_definition_id = transition_row.definition_id "
                "AND item.current_state_id = transition_row.from_state_id "
                "WHERE item.id = :object_id AND transition_row.action_key = :action_key "
                "AND transition_row.enabled = 1 ORDER BY transition_row.sort_order, transition_row.id LIMIT 1"
            ),
            {"object_id": int(object_id), "action_key": payload["action_key"]},
        ).scalar_one_or_none()
    finally:
        db.close()
    if transition_id is None:
        return kwargs
    kwargs["json"] = {"transition_id": int(transition_id), **{key: value for key, value in payload.items() if key != "action_key"}}
    return kwargs


def _adapt_legacy_transition_response(method: str, url: str, response) -> None:
    if method.upper() != "GET" or not url.endswith("/transitions") or response.status_code != 200:
        return
    payload = response.json()
    if not isinstance(payload, list):
        return
    transition_ids = [item.get("transition_id") for item in payload if item.get("transition_id")]
    if not transition_ids:
        return
    db = SessionLocal()
    try:
        action_keys = dict(
            db.execute(
                text("SELECT id, action_key FROM workflow_transitions WHERE id IN :ids"),
                {"ids": tuple(transition_ids)},
            ).all()
        )
    finally:
        db.close()
    for item in payload:
        item["action_key"] = action_keys.get(item.get("transition_id"))
    response._content = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    response.headers["content-length"] = str(len(response._content))


def _adapt_legacy_graph_request(method: str, url: str, kwargs: dict) -> tuple[dict, list[str | None]]:
    payload = kwargs.get("json")
    if method.upper() != "PUT" or not re.search(r"/workflow-definitions/\d+/graph$", url) or not isinstance(payload, dict):
        return kwargs, []
    if not any("action_key" in transition for transition in payload.get("transitions") or []):
        return kwargs, []
    definition_id = int(re.search(r"/workflow-definitions/(\d+)/graph$", url).group(1))
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM workflow_transitions WHERE definition_id = :definition_id"), {"definition_id": definition_id})
        db.commit()
    finally:
        db.close()
    payload = json.loads(json.dumps(payload))
    legacy_keys = []
    for transition in payload.get("transitions") or []:
        legacy_keys.append(transition.pop("action_key", None))
        transition.pop("definition_id", None)
        ui_config = transition.get("ui_config")
        if isinstance(ui_config, dict):
            for key in ("hidden", "list_priority", "visible_in_detail", "visible_in_list"):
                ui_config.pop(key, None)
            ui_config["list_display"] = "primary" if ui_config.get("list_display") == "primary" else "more"
    kwargs["json"] = payload
    return kwargs, legacy_keys


def _restore_legacy_graph_keys(response, legacy_keys: list[str | None]) -> None:
    if response.status_code != 200 or not any(legacy_keys):
        return
    transitions = response.json().get("transitions") or []
    db = SessionLocal()
    try:
        for transition, action_key in zip(transitions, legacy_keys):
            if action_key:
                db.execute(
                    text("UPDATE workflow_transitions SET action_key = :action_key WHERE id = :transition_id"),
                    {"action_key": action_key, "transition_id": transition["id"]},
                )
        db.commit()
    finally:
        db.close()


@pytest.fixture()
def client() -> TestClient:
    before = _snapshot_table_ids()
    default_token = _create_default_admin_token()
    try:
        yield AuthenticatedTestClient(app, default_token=default_token)
    finally:
        _cleanup_created_rows(before)


TRACKED_TABLES = [
    "work_item_iteration_history",
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
