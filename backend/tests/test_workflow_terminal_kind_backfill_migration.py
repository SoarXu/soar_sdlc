import importlib.util
from pathlib import Path

import sqlalchemy as sa


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "20260729_003_backfill_workflow_terminal_kinds.py"
)


def _migration_module():
    assert MIGRATION_PATH.exists(), "workflow terminal kind backfill migration must exist"
    spec = importlib.util.spec_from_file_location("workflow_terminal_kind_backfill", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_backfill_only_classifies_canonical_terminal_state_names_for_enabled_definitions():
    migration = _migration_module()
    engine = sa.create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        connection.execute(sa.text("""
            CREATE TABLE workflow_definitions (
                id INTEGER PRIMARY KEY,
                enabled BOOLEAN NOT NULL
            )
        """))
        connection.execute(sa.text("""
            CREATE TABLE workflow_states (
                id INTEGER PRIMARY KEY,
                definition_id INTEGER NOT NULL,
                status_name VARCHAR(100) NOT NULL,
                category VARCHAR(32) NOT NULL,
                terminal_kind VARCHAR(32) NULL
            )
        """))
        connection.execute(sa.text("INSERT INTO workflow_definitions (id, enabled) VALUES (13, 1), (32, 1), (33, 1), (99, 0)"))
        connection.execute(sa.text("""
            INSERT INTO workflow_states (id, definition_id, status_name, category, terminal_kind) VALUES
                (1, 13, '已完成', 'terminal', NULL),
                (2, 32, '已取消', 'terminal', NULL),
                (3, 33, '已关闭', 'terminal', NULL),
                (4, 33, '已挂起', 'terminal', NULL),
                (5, 33, '已取消', 'normal', NULL),
                (6, 33, '自定义结束', 'terminal', NULL),
                (7, 99, '已完成', 'terminal', NULL),
                (8, 13, '已关闭', 'terminal', 'terminated')
        """))

        connection.execute(migration._backfill_terminal_kind_statement())
        connection.execute(migration._backfill_terminal_kind_statement())
        rows = dict(connection.execute(sa.text("SELECT id, terminal_kind FROM workflow_states ORDER BY id")).all())

    assert rows == {
        1: 'completed', 2: 'terminated', 3: 'completed', 4: 'terminated',
        5: None, 6: None, 7: None, 8: 'terminated',
    }


def test_backfill_terminal_kind_statement_supports_mysql():
    migration = _migration_module()

    statement = str(migration._backfill_terminal_kind_statement('mysql'))

    assert 'JOIN workflow_definitions' in statement
    assert 'CASE' in statement
