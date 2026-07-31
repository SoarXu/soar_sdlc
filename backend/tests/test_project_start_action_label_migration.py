import importlib.util
from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "20260731_001_rename_project_start_action.py"
)


def _migration_module():
    spec = importlib.util.spec_from_file_location("rename_project_start_action", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_project_start_action_label_updates_action_and_form_copy_only():
    migration = _migration_module()

    updates = migration._project_start_label_updates(
        [
            {
                "id": 11,
                "form_config": {"title": "开始", "submit_text": "开始", "fields": []},
            },
            {"id": 12, "form_config": None},
        ]
    )

    assert updates == {
        11: {"title": "启动", "submit_text": "启动", "fields": []},
        12: {"title": "启动", "submit_text": "启动"},
    }


def test_default_project_start_action_is_named_launch():
    from app.services.default_workflow_template_service import graph_for_object_type

    project_start = next(
        transition
        for transition in graph_for_object_type("project").transitions
        if transition.action_key == "start"
    )

    assert project_start.action_name == "启动"
