from pathlib import Path
import re

import pytest

from app.db import schema as runtime_schema
from app.db.session import Base
import app.models  # noqa: F401


BACKEND_ROOT = Path(__file__).parents[1]


def test_core_work_items_have_no_legacy_status_column():
    for table_name in ("requirements", "tasks", "bugs", "projects", "iterations"):
        assert "status" not in Base.metadata.tables[table_name].columns


def test_core_work_item_schemas_do_not_accept_or_return_status_strings():
    for relative_path in (
        "app/views/requirement_view.py",
        "app/views/task_view.py",
        "app/views/bug_view.py",
        "app/views/project_view.py",
        "app/views/iteration_view.py",
    ):
        source = (BACKEND_ROOT / relative_path).read_text(encoding="utf-8")
        assert "Status = Literal" not in source
        assert not re.search(r"^\s+status:\s", source, flags=re.MULTILINE)


def test_core_runtime_never_writes_legacy_status_strings():
    workflow_state_source = (BACKEND_ROOT / "app/services/workflow_state_service.py").read_text(
        encoding="utf-8"
    )
    runtime_source = (BACKEND_ROOT / "app/services/workflow_runtime_service.py").read_text(
        encoding="utf-8"
    )

    assert '"status": initial_state.status_key' not in workflow_state_source
    assert "item.status = resolved_target_status" not in runtime_source
    assert 'task.status = "pending_assignment"' not in runtime_source
    assert "current_state.status_key" not in runtime_source
    assert "def _status_key_for_state" not in runtime_source
    assert "def _state_for_status" not in runtime_source
    assert "_status_candidates" not in runtime_source
    assert "_resolve_target_status" not in runtime_source
    assert "WorkflowTransition.from_status" not in runtime_source
    assert "WorkflowState.status_key" not in runtime_source
    assert ".status = resolved_target_state.status_key" not in runtime_source


def test_project_iteration_services_use_state_identity_only():
    forbidden_by_file = {
        "app/services/project_service.py": (
            "Iteration.status",
            "project.status =",
            "iteration.status =",
            '"status": iteration.status',
        ),
        "app/services/iteration_service.py": (
            "iteration.status =",
            '"status": iteration.status',
            ".status_key",
        ),
        "app/services/requirement_service.py": ("project.status",),
        "app/services/task_service.py": ("project.status",),
        "app/services/bug_service.py": ("iteration.status",),
    }
    for relative_path, forbidden_tokens in forbidden_by_file.items():
        source = (BACKEND_ROOT / relative_path).read_text(encoding="utf-8")
        for token in forbidden_tokens:
            assert token not in source, f"{relative_path} still contains {token}"


def test_workflow_persistence_and_seed_do_not_use_state_codes():
    for relative_path in (
        "app/services/default_workflow_template_service.py",
        "app/services/workflow_definition_service.py",
        "app/services/assignee_rule_config_service.py",
        "scripts/seed_demo_work_items.py",
    ):
        source = (BACKEND_ROOT / relative_path).read_text(encoding="utf-8")
        assert "status_key" not in source, relative_path
        assert "from_status" not in source, relative_path
        assert "to_status" not in source, relative_path


def test_runtime_schema_does_not_recreate_removed_workflow_identity():
    source = (BACKEND_ROOT / "app/db/schema.py").read_text(encoding="utf-8")
    for ddl in (
        "CREATE TABLE handler_transition_rules",
        "ADD COLUMN status_key",
        "ADD COLUMN from_status",
        "ADD COLUMN to_status",
    ):
        assert ddl not in source


def test_runtime_schema_bootstrap_creates_tables_before_ensuring_legacy_shape():
    source = (BACKEND_ROOT / "app/main.py").read_text(encoding="utf-8")
    assert source.index("Base.metadata.create_all(bind=engine)") < source.index(
        "ensure_runtime_schema(engine)"
    )


def test_runtime_schema_ensures_all_workflow_identity_foreign_keys():
    source = (BACKEND_ROOT / "app/db/schema.py").read_text(encoding="utf-8")
    expected_relationships = {
        ("workflow_definitions", "initial_state_id", "workflow_states"),
        ("workflow_states", "definition_id", "workflow_definitions"),
        ("workflow_transitions", "definition_id", "workflow_definitions"),
        ("workflow_transitions", "from_state_id", "workflow_states"),
        ("workflow_transitions", "to_state_id", "workflow_states"),
        ("requirements", "workflow_definition_id", "workflow_definitions"),
        ("requirements", "current_state_id", "workflow_states"),
        ("tasks", "workflow_definition_id", "workflow_definitions"),
        ("tasks", "current_state_id", "workflow_states"),
        ("bugs", "workflow_definition_id", "workflow_definitions"),
        ("bugs", "current_state_id", "workflow_states"),
        ("projects", "workflow_definition_id", "workflow_definitions"),
        ("projects", "current_state_id", "workflow_states"),
        ("iterations", "workflow_definition_id", "workflow_definitions"),
        ("iterations", "current_state_id", "workflow_states"),
    }
    assert "def _ensure_foreign_key" in source
    for table_name, column_name, target_table in expected_relationships:
        assert f'("{table_name}", "{column_name}", "{target_table}"' in source


class _PartialSchemaInspector:
    def get_table_names(self):
        return [
            "requirements",
            "tasks",
            "bugs",
            "projects",
            "iterations",
            "workflow_states",
            "workflow_transitions",
            "handler_transition_rules",
        ]

    def get_columns(self, table_name):
        columns = [{"name": "id", "nullable": False}]
        if table_name in {"requirements", "tasks", "bugs", "projects", "iterations"}:
            columns.extend(
                [
                    {"name": "workflow_definition_id", "nullable": True},
                    {"name": "current_state_id", "nullable": True},
                ]
            )
        if table_name in {"projects", "iterations"}:
            columns.append({"name": "status", "nullable": False})
        if table_name == "workflow_states":
            columns.append({"name": "status_key", "nullable": False})
        if table_name == "workflow_transitions":
            columns.extend(
                [
                    {"name": "from_state_id", "nullable": True},
                    {"name": "to_state_id", "nullable": True},
                    {"name": "from_status", "nullable": False},
                    {"name": "to_status", "nullable": False},
                ]
            )
        return columns


def test_runtime_schema_rejects_partial_legacy_workflow_schema(monkeypatch):
    monkeypatch.setattr(runtime_schema, "inspect", lambda engine: _PartialSchemaInspector())

    with pytest.raises(RuntimeError, match="alembic upgrade head"):
        runtime_schema._validate_final_workflow_schema(object())

    source = (BACKEND_ROOT / "app/db/schema.py").read_text(encoding="utf-8")
    assert "ALTER TABLE projects ADD COLUMN workflow_definition_id" not in source
    assert "ALTER TABLE iterations ADD COLUMN workflow_definition_id" not in source


class _WrongDeleteInspector:
    def get_table_names(self):
        return ["projects", "workflow_definitions"]

    def get_columns(self, table_name):
        return [{"name": "workflow_definition_id" if table_name == "projects" else "id"}]

    def get_foreign_keys(self, table_name):
        return [
            {
                "name": "fk_projects_workflow_definition",
                "constrained_columns": ["workflow_definition_id"],
                "referred_table": "workflow_definitions",
                "referred_columns": ["id"],
                "options": {"ondelete": "CASCADE"},
            }
        ]


def test_runtime_schema_rejects_wrong_foreign_key_delete_semantics(monkeypatch):
    monkeypatch.setattr(runtime_schema, "inspect", lambda engine: _WrongDeleteInspector())

    with pytest.raises(RuntimeError, match="ON DELETE CASCADE.*expected RESTRICT"):
        runtime_schema._ensure_foreign_key(
            object(),
            "projects",
            "workflow_definition_id",
            "workflow_definitions",
            "id",
            "fk_projects_workflow_definition",
            "RESTRICT",
        )


def test_program_and_history_snapshots_remain_available():
    assert "status" in Base.metadata.tables["programs"].columns
    history = Base.metadata.tables["status_operation_log"].columns
    assert "from_status" in history
    assert "to_status" in history


def test_migration_audit_script_exists_and_checks_cross_definition_references():
    source = (BACKEND_ROOT / "scripts/audit_workflow_state_migration.py").read_text(encoding="utf-8")

    assert "invalid_current_state_definition" in source
    assert "invalid_transition_definition" in source
    assert "invalid_initial_state_definition" in source
    assert '"projects"' in source
    assert '"iterations"' in source
    assert "legacy_workflow_column" in source
    assert "legacy_handler_rule_table" in source


def test_transition_handler_rule_is_the_only_assignee_routing_source():
    assert "handler_transition_rules" not in Base.metadata.tables
    for relative_path in (
        "app/models/handler_transition_rule.py",
        "app/views/handler_transition_rule_view.py",
        "app/services/handler_transition_rule_service.py",
        "app/controllers/handler_transition_rule_controller.py",
    ):
        assert not (BACKEND_ROOT / relative_path).exists()

    router_source = (BACKEND_ROOT / "app/controllers/router.py").read_text(encoding="utf-8")
    definition_source = (BACKEND_ROOT / "app/services/workflow_definition_service.py").read_text(encoding="utf-8")
    scheme_source = (BACKEND_ROOT / "app/services/assignee_rule_config_service.py").read_text(encoding="utf-8")
    assert "handler_transition_rule_controller" not in router_source
    assert "_sync_handler_rules" not in definition_source
    assert "_clone_additional_handler_rules" not in scheme_source
