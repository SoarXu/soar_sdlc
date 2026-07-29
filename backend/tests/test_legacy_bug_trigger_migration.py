import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "20260729_002_remove_legacy_bug_trigger.py"
)


def _migration_module():
    assert MIGRATION_PATH.exists(), "legacy Bug trigger cleanup migration must exist"
    spec = importlib.util.spec_from_file_location("remove_legacy_bug_trigger", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_legacy_bug_trigger_cleanup_only_clears_the_known_empty_marker():
    migration = _migration_module()
    engine = sa.create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        connection.execute(sa.text("""
            CREATE TABLE workflow_transitions (
                id INTEGER PRIMARY KEY,
                definition_id INTEGER NOT NULL,
                trigger_config JSON NULL
            )
        """))
        connection.execute(sa.text("""
            INSERT INTO workflow_transitions (id, definition_id, trigger_config) VALUES
                (136, 33, '{"type": "legacy_script"}'),
                (137, 33, '{"type": "notification", "receiver": "actor", "title": "Kept"}'),
                (999, 99, '{"type": "legacy_script"}')
        """))

        connection.execute(migration._remove_legacy_bug_trigger_statement())
        connection.execute(migration._remove_legacy_bug_trigger_statement())
        cleaned = dict(connection.execute(
            sa.select(
                migration._TRANSITIONS.c.id,
                migration._TRANSITIONS.c.trigger_config,
            ).order_by(migration._TRANSITIONS.c.id)
        ).all())

    assert cleaned[136] is None
    assert cleaned[137] == {"type": "notification", "receiver": "actor", "title": "Kept"}
    assert cleaned[999] == {"type": "legacy_script"}


def test_legacy_bug_trigger_cleanup_preserves_a_future_payload():
    migration = _migration_module()
    engine = sa.create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        connection.execute(sa.text("""
            CREATE TABLE workflow_transitions (
                id INTEGER PRIMARY KEY,
                definition_id INTEGER NOT NULL,
                trigger_config JSON NULL
            )
        """))
        connection.execute(sa.text("""
            INSERT INTO workflow_transitions (id, definition_id, trigger_config) VALUES
                (136, 33, '{"type": "legacy_script", "script": "preserve-me"}')
        """))

        connection.execute(migration._remove_legacy_bug_trigger_statement())
        trigger_config = connection.scalar(
            sa.select(migration._TRANSITIONS.c.trigger_config)
        )

    assert trigger_config == {"type": "legacy_script", "script": "preserve-me"}


def test_legacy_bug_trigger_cleanup_rejects_unsupported_dialects():
    migration = _migration_module()

    with pytest.raises(RuntimeError, match="Unsupported database dialect: postgresql"):
        migration._remove_legacy_bug_trigger_statement("postgresql")
