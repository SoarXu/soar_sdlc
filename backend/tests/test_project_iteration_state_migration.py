import importlib.util
from pathlib import Path

import pytest


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "20260717_001_project_iteration_state_identity.py"
)


def _migration_module():
    spec = importlib.util.spec_from_file_location("project_iteration_state_identity", MIGRATION_PATH)
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
