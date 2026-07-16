import importlib.util
from pathlib import Path

import pytest


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "20260716_001_workflow_state_identity.py"
)


def _migration_module():
    spec = importlib.util.spec_from_file_location("workflow_state_identity_migration", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_maps_canonical_work_item_statuses_to_legacy_scheme_state_keys():
    migration = _migration_module()
    states = [
        {"id": 11, "status_key": "draft", "status_name": "待梳理", "category": "start"},
        {"id": 12, "status_key": "active", "status_name": "方案处理中", "category": "normal"},
        {"id": 13, "status_key": "done", "status_name": "方案完成", "category": "terminal"},
    ]

    assert migration._match_state_id(states, "requirement", "pending_assignment", owner_id=None) == 11
    assert migration._match_state_id(states, "requirement", "in_processing", owner_id=8) == 12
    assert migration._match_state_id(states, "requirement", "completed", owner_id=8) == 13


@pytest.mark.parametrize(
    ("object_type", "status_value", "legacy_key"),
    [
        ("task", "pending_assignment", "todo"),
        ("task", "in_processing", "doing"),
        ("bug", "pending_handling", "open"),
        ("bug", "pending_verification", "verifying"),
    ],
)
def test_migration_supports_known_task_and_bug_aliases(object_type, status_value, legacy_key):
    migration = _migration_module()
    states = [{"id": 21, "status_key": legacy_key, "status_name": "自定义中文名", "category": "normal"}]

    assert migration._match_state_id(states, object_type, status_value, owner_id=None) == 21


def test_migration_prefers_exact_state_key_and_rejects_unmappable_values():
    migration = _migration_module()
    states = [
        {"id": 31, "status_key": "pending_assignment", "status_name": "精确节点", "category": "start"},
        {"id": 32, "status_key": "draft", "status_name": "历史节点", "category": "start"},
    ]

    assert migration._match_state_id(states, "requirement", "pending_assignment", owner_id=None) == 31
    with pytest.raises(ValueError, match="requirement 99.*unknown_status"):
        migration._match_state_id(
            states,
            "requirement",
            "unknown_status",
            owner_id=None,
            object_id=99,
        )


def test_migration_requires_one_initial_state_per_definition():
    migration = _migration_module()
    states = [
        {"id": 41, "status_key": "draft", "status_name": "开始一", "category": "start"},
        {"id": 42, "status_key": "backlog", "status_name": "开始二", "category": "start"},
    ]

    with pytest.raises(ValueError, match="definition 7.*exactly one initial state"):
        migration._initial_state_id(states, definition_id=7)
