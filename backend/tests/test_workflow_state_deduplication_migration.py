import importlib.util
import json
from pathlib import Path

import pytest
import sqlalchemy as sa


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "20260720_001_deduplicate_disabled_workflow_states.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("workflow_state_deduplication", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _schema(bind):
    bind.execute(sa.text(
        "CREATE TABLE workflow_states ("
        "id INTEGER PRIMARY KEY, definition_id INTEGER NOT NULL, "
        "status_name TEXT NOT NULL, enabled INTEGER NOT NULL)"
    ))
    bind.execute(sa.text(
        "CREATE TABLE workflow_definitions (id INTEGER PRIMARY KEY, initial_state_id INTEGER)"
    ))
    bind.execute(sa.text(
        "CREATE TABLE workflow_transitions ("
        "id INTEGER PRIMARY KEY, from_state_id INTEGER, to_state_id INTEGER, condition_config TEXT)"
    ))
    for table in ("requirements", "tasks", "bugs", "projects", "iterations"):
        bind.execute(sa.text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, current_state_id INTEGER)"))
    bind.execute(sa.text(
        "CREATE TABLE status_operation_log ("
        "id INTEGER PRIMARY KEY, from_state_id INTEGER, to_state_id INTEGER)"
    ))


def test_planner_merges_only_disabled_states_with_one_enabled_match():
    migration = _load_migration()
    states = [
        {"id": 10, "definition_id": 7, "status_name": "待分派", "enabled": 1},
        {"id": 11, "definition_id": 7, "status_name": "待分派", "enabled": 0},
        {"id": 20, "definition_id": 8, "status_name": "待分派", "enabled": 1},
        {"id": 21, "definition_id": 8, "status_name": "待分派", "enabled": 0},
    ]

    assert migration._plan_duplicate_state_merges(states) == {11: 10, 21: 20}


def test_planner_skips_ambiguous_and_missing_enabled_targets_with_stable_diagnostics():
    migration = _load_migration()
    states = [
        {"id": 31, "definition_id": 9, "status_name": "无目标", "enabled": 0},
        {"id": 42, "definition_id": 10, "status_name": "多目标", "enabled": 1},
        {"id": 41, "definition_id": 10, "status_name": "多目标", "enabled": 1},
        {"id": 43, "definition_id": 10, "status_name": "多目标", "enabled": 0},
    ]

    merges, diagnostics = migration._plan_duplicate_state_merges_with_diagnostics(states)

    assert merges == {}
    assert diagnostics == [
        {
            "definition_id": 9,
            "status_name": "无目标",
            "disabled_ids": [31],
            "enabled_ids": [],
            "reason": "no_enabled_match",
        },
        {
            "definition_id": 10,
            "status_name": "多目标",
            "disabled_ids": [43],
            "enabled_ids": [41, 42],
            "reason": "ambiguous_enabled_match",
        },
    ]


def test_condition_config_remaps_only_explicit_state_reference_maps():
    migration = _load_migration()
    source = {
        "routes": {"approved": 11, "rejected": 12},
        "target_state_id_by_owner": {"owner": 11},
        "threshold": 11,
        "nested": {"state": 11},
    }

    remapped = migration._remap_condition_config(source, {11: 10})

    assert remapped == {
        "routes": {"approved": 10, "rejected": 12},
        "target_state_id_by_owner": {"owner": 10},
        "threshold": 11,
        "nested": {"state": 11},
    }
    assert source["routes"]["approved"] == 11


def test_execute_migration_updates_every_reference_before_deleting_duplicate():
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as bind:
        _schema(bind)
        bind.execute(sa.text(
            "INSERT INTO workflow_states (id, definition_id, status_name, enabled) "
            "VALUES (10, 7, 'Done', 1), (11, 7, 'Done', 0)"
        ))
        bind.execute(sa.text("INSERT INTO workflow_definitions VALUES (7, 11)"))
        for table in ("requirements", "tasks", "bugs", "projects", "iterations"):
            bind.execute(sa.text(f"INSERT INTO {table} VALUES (1, 11)"))
        bind.execute(sa.text("INSERT INTO status_operation_log VALUES (1, 11, 11)"))
        bind.execute(
            sa.text("INSERT INTO workflow_transitions VALUES (1, 11, 11, :config)"),
            {"config": json.dumps({"routes": {"done": 11}, "threshold": 11})},
        )

        diagnostics = migration._execute_migration(bind)

        assert diagnostics == []
        assert bind.execute(sa.text("SELECT id FROM workflow_states ORDER BY id")).scalars().all() == [10]
        assert bind.execute(sa.text("SELECT initial_state_id FROM workflow_definitions")).scalar_one() == 10
        for table in ("requirements", "tasks", "bugs", "projects", "iterations"):
            assert bind.execute(sa.text(f"SELECT current_state_id FROM {table}")).scalar_one() == 10
        log = bind.execute(sa.text(
            "SELECT from_state_id, to_state_id FROM status_operation_log"
        )).one()
        assert tuple(log) == (10, 10)
        transition = bind.execute(sa.text(
            "SELECT from_state_id, to_state_id, condition_config FROM workflow_transitions"
        )).one()
        assert tuple(transition[:2]) == (10, 10)
        assert json.loads(transition.condition_config) == {"routes": {"done": 10}, "threshold": 11}


def test_execute_migration_audits_all_references_before_any_delete(monkeypatch):
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as bind:
        _schema(bind)
        bind.execute(sa.text(
            "INSERT INTO workflow_states (id, definition_id, status_name, enabled) "
            "VALUES (10, 7, 'Done', 1), (11, 7, 'Done', 0)"
        ))
        bind.execute(
            sa.text("INSERT INTO workflow_transitions VALUES (1, 10, 10, :config)"),
            {"config": json.dumps({"routes": {"done": 11}})},
        )
        monkeypatch.setattr(migration, "_update_condition_configs", lambda bind, merges: None)

        with pytest.raises(RuntimeError, match="condition_config"):
            migration._execute_migration(bind)

        assert bind.execute(sa.text(
            "SELECT COUNT(*) FROM workflow_states WHERE id = 11"
        )).scalar_one() == 1


def test_execute_migration_reports_ambiguous_group_without_deleting_it():
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as bind:
        _schema(bind)
        bind.execute(sa.text(
            "INSERT INTO workflow_states (id, definition_id, status_name, enabled) VALUES "
            "(10, 7, 'Done', 1), (12, 7, 'Done', 1), (11, 7, 'Done', 0)"
        ))

        diagnostics = migration._execute_migration(bind)

        assert diagnostics[0]["reason"] == "ambiguous_enabled_match"
        assert bind.execute(sa.text(
            "SELECT id FROM workflow_states ORDER BY id"
        )).scalars().all() == [10, 11, 12]
