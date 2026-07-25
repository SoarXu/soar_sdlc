import importlib.util
from pathlib import Path


MIGRATION_CANDIDATES = list(
    (Path(__file__).parents[1] / "alembic" / "versions").glob("*_promote_project_start_action.py")
)


def _migration_module():
    assert len(MIGRATION_CANDIDATES) == 1, "project start action migration must exist"
    spec = importlib.util.spec_from_file_location("promote_project_start_action", MIGRATION_CANDIDATES[0])
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_promotes_project_start_and_preserves_other_ui_config():
    migration = _migration_module()

    updates = migration._project_start_updates([
        {"id": 1, "ui_config": {"list_display": "more", "button_type": "success"}},
        {"id": 2, "ui_config": None},
    ])

    assert updates == {
        1: {"list_display": "primary", "button_type": "success"},
        2: {"list_display": "primary"},
    }
