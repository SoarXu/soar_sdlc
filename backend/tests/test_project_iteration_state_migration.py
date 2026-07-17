import importlib.util
import json
from pathlib import Path

import pytest


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "20260717_001_project_iteration_state_identity.py"
)
FINALIZATION_MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "20260717_002_remove_workflow_state_strings.py"
)


def _migration_module():
    spec = importlib.util.spec_from_file_location("project_iteration_state_identity", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _finalization_migration_module():
    spec = importlib.util.spec_from_file_location(
        "remove_workflow_state_strings",
        FINALIZATION_MIGRATION_PATH,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("object_type", "status_value", "expected_id"),
    [
        ("project", "planning", 11),
        ("project", "active", 12),
        ("project", "paused", 13),
        ("project", "closed", 14),
        ("iteration", "planning", 21),
        ("iteration", "active", 22),
        ("iteration", "completed", 23),
        ("iteration", "canceled", 24),
    ],
)
def test_project_iteration_migration_maps_exact_state_keys(object_type, status_value, expected_id):
    migration = _migration_module()
    states = {
        "project": [
            {"id": 11, "status_key": "planning"},
            {"id": 12, "status_key": "active"},
            {"id": 13, "status_key": "paused"},
            {"id": 14, "status_key": "closed"},
        ],
        "iteration": [
            {"id": 21, "status_key": "planning"},
            {"id": 22, "status_key": "active"},
            {"id": 23, "status_key": "completed"},
            {"id": 24, "status_key": "canceled"},
        ],
    }

    assert migration._match_state_id(states[object_type], object_type, 99, status_value) == expected_id


def test_project_iteration_migration_rejects_unknown_and_ambiguous_states():
    migration = _migration_module()

    with pytest.raises(ValueError, match="project 41.*unknown"):
        migration._match_state_id([], "project", 41, "unknown")

    duplicate = [
        {"id": 31, "status_key": "active"},
        {"id": 32, "status_key": "active"},
    ]
    with pytest.raises(ValueError, match="iteration 42.*ambiguous"):
        migration._match_state_id(duplicate, "iteration", 42, "active")


def test_project_iteration_migration_targets_only_confirmed_objects():
    migration = _migration_module()

    assert migration._legacy_status_tables() == {
        "projects": "project",
        "iterations": "iteration",
    }


class _ScalarOneOrNone:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _TransitionCaptureBind:
    def __init__(self, scalar_value=None):
        self.calls = []
        self.scalar_value = scalar_value

    def execute(self, statement, params=None):
        self.calls.append((str(statement), params or {}))
        return _ScalarOneOrNone(self.scalar_value)


def test_existing_project_activate_short_circuits_before_legacy_state_lookup(monkeypatch):
    migration = _migration_module()
    bind = _TransitionCaptureBind(scalar_value=45448)
    monkeypatch.setattr(migration, "_system_definition", lambda _bind, _object_type: 7)
    monkeypatch.setattr(
        migration,
        "_definition_states",
        lambda _bind, _definition_id: [
            {"id": 11, "status_key": "state_11"},
            {"id": 12, "status_key": "state_12"},
        ],
    )

    migration._ensure_project_activate_transition(bind)

    assert not any("INSERT INTO workflow_transitions" in sql for sql, _params in bind.calls)
    lookup_sql = bind.calls[0][0]
    assert "source_state.category = 'terminal'" in lookup_sql
    assert "target_state.category <> 'terminal'" in lookup_sql


def test_project_activate_transition_insert_is_marked_as_owned_by_migration(monkeypatch):
    migration = _migration_module()
    bind = _TransitionCaptureBind()
    monkeypatch.setattr(migration, "_system_definition", lambda _bind, _object_type: 7)
    monkeypatch.setattr(
        migration,
        "_definition_states",
        lambda _bind, _definition_id: [
            {"id": 11, "status_key": "closed"},
            {"id": 12, "status_key": "active"},
        ],
    )

    migration._ensure_project_activate_transition(bind)

    insert_sql, insert_params = next(
        (sql, params) for sql, params in bind.calls if "INSERT INTO workflow_transitions" in sql
    )
    assert "ui_config" in insert_sql
    assert json.loads(insert_params["ui_config"]) == {
        "migration_origin": "20260717_001"
    }


def test_project_activate_transition_downgrade_deletes_only_migration_owned_edge(monkeypatch):
    migration = _migration_module()
    bind = _TransitionCaptureBind()
    monkeypatch.setattr(migration.op, "get_bind", lambda: bind)
    monkeypatch.setattr(migration, "_legacy_status_tables", lambda: {})

    migration.downgrade()

    delete_sql, delete_params = next(
        (sql, params) for sql, params in bind.calls if "DELETE" in sql
    )
    assert "JSON_EXTRACT" in delete_sql
    assert "$.migration_origin" in delete_sql
    assert delete_params == {"migration_origin": "20260717_001"}


def test_finalization_migration_has_deterministic_audit_diagnostic():
    migration = _finalization_migration_module()
    issues = [
        {"issue": "null_workflow_reference", "table": "projects", "ids": [9, 2]},
        {"issue": "invalid_transition_definition", "table": "workflow_transitions", "ids": [7]},
    ]

    assert migration._format_audit_issues(issues) == (
        "Workflow state finalization audit failed: "
        "invalid_transition_definition[workflow_transitions]=7; "
        "null_workflow_reference[projects]=2,9"
    )


def test_finalization_migration_declares_all_removed_identity_storage():
    migration = _finalization_migration_module()

    assert migration._legacy_columns() == {
        "projects": ("status",),
        "iterations": ("status",),
        "workflow_states": ("status_key",),
        "workflow_transitions": ("from_status", "to_status"),
    }
    assert migration._legacy_handler_rule_table() == "handler_transition_rules"


class _ScalarRows:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


class _CoreReferenceAuditBind:
    def execute(self, statement):
        sql = str(statement)
        for position, table_name in enumerate(
            ("requirements", "tasks", "bugs", "projects", "iterations"),
            start=101,
        ):
            if f"SELECT id FROM {table_name}" in sql and "IS NULL" in sql:
                return _ScalarRows([position])
            if f"SELECT item.id FROM {table_name} item" in sql:
                return _ScalarRows([position + 100])
        return _ScalarRows([])


def test_finalization_migration_blocks_null_references_for_all_core_objects(monkeypatch):
    migration = _finalization_migration_module()
    monkeypatch.setattr(migration, "_table_names", lambda: set())

    with pytest.raises(RuntimeError) as exc_info:
        migration._audit_or_raise(_CoreReferenceAuditBind())

    diagnostic = str(exc_info.value)
    for table_name in ("requirements", "tasks", "bugs", "projects", "iterations"):
        assert f"null_workflow_reference[{table_name}]" in diagnostic
        assert f"invalid_current_state_definition[{table_name}]" in diagnostic


def test_finalization_audits_only_non_null_initial_state_references():
    migration_source = FINALIZATION_MIGRATION_PATH.read_text(encoding="utf-8")
    audit_source = (
        Path(__file__).parents[1] / "scripts" / "audit_workflow_state_migration.py"
    ).read_text(encoding="utf-8")

    for source in (migration_source, audit_source):
        assert "definition.initial_state_id IS NOT NULL" in source
        assert "definition.initial_state_id IS NULL OR" not in source


def _legacy_handler_rule(rule_id=1, **overrides):
    rule = {
        "id": rule_id,
        "config_id": 81,
        "object_type": "task",
        "action": "claim",
        "from_status": "pending",
        "to_status": "active",
        "target_type": "actor",
        "target_roles": "developer",
        "fallback_type": "project_role",
        "fallback_roles": "project_owner",
    }
    rule.update(overrides)
    return rule


def _handler_transition(transition_id=91, **overrides):
    transition = {
        "id": transition_id,
        "config_id": 81,
        "object_type": "task",
        "action": "claim",
        "from_status": "pending",
        "to_status": "active",
        "handler_rule": None,
    }
    transition.update(overrides)
    return transition


def test_enabled_legacy_handler_rule_uniquely_migrates_to_transition_json():
    migration = _finalization_migration_module()

    updates, issues = migration._plan_handler_rule_migration(
        [_legacy_handler_rule()],
        [_handler_transition()],
    )

    assert issues == []
    assert updates == {
        91: {
            "target_type": "actor",
            "target_roles": "developer",
            "fallback_type": "project_role",
            "fallback_roles": "project_owner",
        }
    }


def test_matching_existing_transition_handler_rule_is_not_overwritten():
    migration = _finalization_migration_module()
    existing = {
        "target_type": "actor",
        "target_roles": "developer",
        "fallback_type": "project_role",
        "fallback_roles": "project_owner",
        "allow_manual_owner": True,
    }

    updates, issues = migration._plan_handler_rule_migration(
        [_legacy_handler_rule()],
        [_handler_transition(handler_rule=existing)],
    )

    assert issues == []
    assert updates == {}


@pytest.mark.parametrize(
    ("candidates", "expected_issue"),
    [
        ([], "unmapped_handler_rule"),
        ([_handler_transition(91), _handler_transition(92)], "ambiguous_handler_rule"),
        (
            [_handler_transition(handler_rule={"target_type": "fixed_user"})],
            "conflicting_handler_rule",
        ),
    ],
)
def test_enabled_legacy_handler_rule_rejects_lossy_mapping(candidates, expected_issue):
    migration = _finalization_migration_module()

    updates, issues = migration._plan_handler_rule_migration(
        [_legacy_handler_rule(rule_id=7)],
        candidates,
    )

    assert updates == {}
    assert issues == [
        {"issue": expected_issue, "table": "handler_transition_rules", "ids": [7]}
    ]


def test_downgrade_reconstructs_expressible_legacy_handler_rule():
    migration = _finalization_migration_module()
    transition = _handler_transition(
        handler_rule={
            "target_type": "actor",
            "target_roles": "developer",
            "fallback_type": "project_role",
            "fallback_roles": "project_owner",
            "allow_manual_owner": True,
        }
    )

    assert migration._legacy_rule_from_transition(transition) == {
        "config_id": 81,
        "rule_type": "advanced",
        "object_type": "task",
        "action": "claim",
        "from_status": "pending",
        "to_status": "active",
        "target_type": "actor",
        "target_roles": "developer",
        "fallback_type": "project_role",
        "fallback_roles": "project_owner",
        "enabled": 1,
    }
