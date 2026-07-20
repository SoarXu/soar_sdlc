import importlib.util
from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "20260720_001_normalize_workflow_transition_buttons.py"
)


def _migration_module():
    spec = importlib.util.spec_from_file_location("normalize_workflow_transition_buttons", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_normalization_disables_hidden_and_rewrites_group_local_order():
    migration = _migration_module()
    rows = [
        {
            "id": 1,
            "definition_id": 8,
            "from_state_id": 11,
            "enabled": 1,
            "sort_order": 90,
            "ui_config": {"list_display": "primary", "list_priority": 20, "visible_in_list": True},
        },
        {
            "id": 2,
            "definition_id": 8,
            "from_state_id": 11,
            "enabled": 1,
            "sort_order": 10,
            "ui_config": {"list_display": "primary", "list_priority": 10},
        },
        {
            "id": 3,
            "definition_id": 8,
            "from_state_id": 11,
            "enabled": 1,
            "sort_order": 30,
            "ui_config": {"list_display": "hidden", "hidden": True},
        },
    ]

    updates = migration._normalization_updates(rows)

    assert updates[2]["sort_order"] == 10
    assert updates[1]["sort_order"] == 20
    assert updates[1]["ui_config"] == {"list_display": "primary"}
    assert updates[3] == {
        "enabled": False,
        "sort_order": 10,
        "ui_config": {"list_display": "more"},
        "form_config": None,
    }


def test_normalization_adds_fixed_effective_date_forms_to_legacy_project_transitions():
    migration = _migration_module()
    rows = [
        {
            "id": 1,
            "definition_id": 8,
            "object_type": "project",
            "action_key": "start",
            "from_state_id": 11,
            "enabled": 1,
            "sort_order": 10,
            "ui_config": {"list_display": "primary"},
            "form_config": None,
        },
        {
            "id": 2,
            "definition_id": 8,
            "object_type": "project",
            "action_key": "close",
            "from_state_id": 12,
            "enabled": 1,
            "sort_order": 10,
            "ui_config": {"list_display": "primary"},
            "form_config": None,
        },
        {
            "id": 3,
            "definition_id": 9,
            "object_type": "requirement",
            "action_key": "close",
            "from_state_id": 13,
            "enabled": 1,
            "sort_order": 10,
            "ui_config": {"list_display": "primary"},
            "form_config": {"fields": [{"field": "reason"}]},
        },
    ]

    updates = migration._normalization_updates(rows)

    assert updates[1]["form_config"] == {
        "fields": [{"field": "effective_time", "label": "实际开始日期", "type": "date", "required": True}]
    }
    assert updates[2]["form_config"] == {
        "fields": [{"field": "effective_time", "label": "实际完成日期", "type": "date", "required": True}]
    }
    assert updates[3]["form_config"] == {"fields": [{"field": "reason"}]}
