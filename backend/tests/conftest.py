from datetime import datetime
import json
import pytest
import re
from sqlalchemy import text

from app.testing.database import prepare_test_database_from_environment


prepare_test_database_from_environment()

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User
from app.services.default_workflow_template_service import ensure_default_workflow_templates
from app.services.role_service import seed_default_roles


def _prepare_test_reference_data() -> None:
    db = SessionLocal()
    try:
        password_hash = get_password_hash("test-only-password")
        for username in TEST_USER_ALLOWLIST:
            if db.query(User).filter(User.username == username).first() is None:
                db.add(
                    User(
                        username=username,
                        full_name=username,
                        password_hash=password_hash,
                        department="Test",
                        is_active=True,
                        is_system_admin=username == TEST_ADMIN_USERNAME,
                        must_change_password=False,
                        deleted=0,
                    )
                )
        db.flush()
        db.query(User).filter(User.username.in_(TEST_USER_ALLOWLIST)).update(
            {User.deleted: 0, User.is_active: True, User.delete_time: None},
            synchronize_session=False,
        )
        db.query(User).filter(User.username == TEST_ADMIN_USERNAME).update(
            {User.is_system_admin: True},
            synchronize_session=False,
        )
        db.commit()
        seed_default_roles(db)
        ensure_default_workflow_templates(db, reconcile_existing=True)
    finally:
        db.close()


TEST_USER_ALLOWLIST = frozenset(
    {
        "shuwan.yang",
        "bob",
        "tao.qu",
        "wenyan.zhao",
        "yanan.liu",
        "xinlin.jiang",
        "zheng.xu",
        "xiang.xu",
    }
)
TEST_ADMIN_USERNAME = "shuwan.yang"


_prepare_test_reference_data()


class AuthenticatedTestClient(TestClient):
    def __init__(self, *args, default_token: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_token = default_token
        self._real_iteration_defaults_enabled = False
        self._real_iteration_defaults: dict[int, int] = {}
        self._active_real_iteration_defaults: set[int] = set()

    def enable_real_iteration_defaults(self) -> None:
        self._real_iteration_defaults_enabled = True

    def request(self, method: str, url, **kwargs):
        headers = dict(kwargs.pop("headers", {}) or {})
        skip_default_auth = headers.pop("X-Test-No-Auth", None)
        skip_transition_adapter = headers.pop("X-Test-Raw-Transition-Request", None)
        require_explicit_iteration = headers.pop("X-Test-Require-Explicit-Iteration", None)
        legacy_graph_keys = []
        if not skip_transition_adapter:
            kwargs = _adapt_legacy_transition_request(method, str(url), kwargs)
            kwargs, legacy_graph_keys = _adapt_legacy_graph_request(method, str(url), kwargs)
        if not skip_default_auth and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {self.default_token}"
        if (
            method.upper() == "POST"
            and (
                (
                    self._real_iteration_defaults_enabled
                    and str(url).rstrip("/").endswith("/api/v1/requirements")
                )
                or (
                    not require_explicit_iteration
                    and str(url).rstrip("/").endswith("/api/v1/bugs")
                )
            )
            and isinstance(kwargs.get("json"), dict)
            and "iteration_id" not in kwargs["json"]
        ):
            project_id = kwargs["json"].get("project_id")
            if project_id and project_id not in self._real_iteration_defaults:
                iteration_response = super().request(
                    "POST",
                    "/api/v1/iterations",
                    json={"name": f"Test iteration {project_id}", "project_ids": [project_id]},
                    headers={"Authorization": f"Bearer {self.default_token}"},
                )
                assert iteration_response.status_code == 200, iteration_response.text
                self._real_iteration_defaults[project_id] = iteration_response.json()["id"]
            if (
                project_id in self._real_iteration_defaults
                and str(url).rstrip("/").endswith("/api/v1/bugs")
                and project_id not in self._active_real_iteration_defaults
            ):
                started = self.request(
                    "POST",
                    f"/api/v1/workflow-runtime/iteration/{self._real_iteration_defaults[project_id]}/transition",
                    json={"action_key": "start"},
                )
                assert started.status_code == 200, started.text
                self._active_real_iteration_defaults.add(project_id)
            if project_id in self._real_iteration_defaults:
                kwargs["json"] = {
                    **kwargs["json"],
                    "iteration_id": self._real_iteration_defaults[project_id],
                }
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
    default_token = _test_admin_token()
    try:
        yield AuthenticatedTestClient(app, default_token=default_token)
    finally:
        _cleanup_created_rows(before)


@pytest.fixture(autouse=True)
def enforce_test_user_whitelist():
    _deactivate_non_allowlisted_users()
    try:
        yield
    finally:
        _deactivate_non_allowlisted_users()


TRACKED_TABLES = [
    "workflow_migration_logs",
    "work_item_components",
    "business_component_transition_routes",
    "business_component_members",
    "business_components",
    "work_item_iteration_history",
    "exception_rules",
    "bug_types",
    "devops_code_review_tasks",
    "work_item_review_rounds",
    "devops_git_platform_connections",
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
    "project_members",
    "projects",
    "workflow_transitions",
    "workflow_states",
    "workflow_definitions",
    "iterations",
    "assignee_rule_configs",
    "programs",
    "user_roles",
    "users",
    "roles",
]


def _snapshot_table_ids() -> dict[str, set[int]]:
    db = SessionLocal()
    try:
        # State-matrix reconciliation may add nodes to long-lived default definitions.
        # Establish that baseline before each client snapshot so fixture cleanup only
        # removes rows introduced by the test itself.
        ensure_default_workflow_templates(db, reconcile_existing=True)
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
                if table == "tasks":
                    db.execute(
                        text("update tasks set parent_task_id = null where parent_task_id in :ids"),
                        {"ids": tuple(created_ids)},
                    )
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


def _deactivate_non_allowlisted_users() -> int:
    db = SessionLocal()
    try:
        updated = (
            db.query(User)
            .filter(User.deleted == 0, User.username.not_in(TEST_USER_ALLOWLIST))
            .update(
                {
                    User.deleted: 1,
                    User.is_active: False,
                    User.delete_time: datetime.now(),
                },
                synchronize_session=False,
            )
        )
        db.commit()
        return int(updated or 0)
    finally:
        db.close()


def _test_admin_token() -> str:
    db = SessionLocal()
    try:
        user = (
            db.query(User)
            .filter(
                User.username == TEST_ADMIN_USERNAME,
                User.deleted == 0,
                User.is_active.is_(True),
            )
            .first()
        )
        if not user:
            raise RuntimeError(f"Missing active test administrator: {TEST_ADMIN_USERNAME}")
        if not user.is_system_admin:
            raise RuntimeError(f"Test administrator is not a system administrator: {TEST_ADMIN_USERNAME}")
        return create_access_token(user.username)
    finally:
        db.close()
