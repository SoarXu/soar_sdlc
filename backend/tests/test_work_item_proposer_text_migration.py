import importlib.util
from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic/versions/20260826_001_work_item_proposer_text.py"
)


def _migration_module():
    spec = importlib.util.spec_from_file_location("work_item_proposer_text_migration", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_normalizes_all_legacy_handler_sources():
    migration = _migration_module()
    original = {
        "target_type": "reporter",
        "fallback_type": "proposer",
        "fallback_chain": [
            {"type": "bug_reporter", "fixed_user_id": 7},
            {"type": "project_owner"},
        ],
    }

    normalized = migration._normalize_handler_rule(original)

    assert normalized == {
        "target_type": "keep_current",
        "fallback_type": "keep_current",
        "fallback_chain": [
            {"type": "keep_current", "fixed_user_id": 7},
            {"type": "project_owner"},
        ],
    }
    assert original["target_type"] == "reporter"
