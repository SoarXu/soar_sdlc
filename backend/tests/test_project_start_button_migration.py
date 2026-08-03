import importlib.util
from pathlib import Path


MIGRATION_CANDIDATES = list(
    (Path(__file__).parents[1] / "alembic" / "versions").glob("*_set_project_start_button_success.py")
)


def _migration_module():
    assert len(MIGRATION_CANDIDATES) == 1, "project start action migration must exist"
    spec = importlib.util.spec_from_file_location("set_project_start_button_success", MIGRATION_CANDIDATES[0])
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_sets_project_start_success_color_and_preserves_other_ui_config():
    migration = _migration_module()

    updates = migration._project_start_updates([
        {"id": 1, "ui_config": {"list_display": "more", "list_priority": 20}},
        {"id": 2, "ui_config": None},
    ])

    assert updates == {
        1: {"list_display": "more", "list_priority": 20, "button_type": "success"},
        2: {"button_type": "success"},
    }


def test_default_project_start_action_uses_success_button_type():
    from app.services.default_workflow_template_service import graph_for_object_type

    project_start = next(
        transition
        for transition in graph_for_object_type("project").transitions
        if transition.action_key == "start"
    )

    assert project_start.ui_config["button_type"] == "success"
