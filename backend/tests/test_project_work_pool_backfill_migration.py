import importlib.util
from pathlib import Path

import sqlalchemy as sa


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "20260806_002_backfill_project_work_pool_items.py"
)


def _migration_module():
    assert MIGRATION_PATH.exists(), "project work-pool backfill migration must exist"
    spec = importlib.util.spec_from_file_location("project_work_pool_backfill", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_schema(bind) -> None:
    bind.execute(sa.text(
        "CREATE TABLE projects ("
        "id INTEGER PRIMARY KEY, requirement_pool_iteration_id INTEGER)"
    ))
    bind.execute(sa.text(
        "CREATE TABLE workflow_states ("
        "id INTEGER PRIMARY KEY, category TEXT NOT NULL)"
    ))
    for table_name in ("requirements", "tasks", "bugs"):
        bind.execute(sa.text(
            f"CREATE TABLE {table_name} ("
            "id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL, iteration_id INTEGER, "
            "current_state_id INTEGER NOT NULL, deleted INTEGER NOT NULL)"
        ))
    bind.execute(sa.text(
        "CREATE TABLE work_item_iteration_history ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, object_type TEXT NOT NULL, "
        "object_id INTEGER NOT NULL, iteration_id INTEGER NOT NULL, "
        "entered_at DATETIME DEFAULT CURRENT_TIMESTAMP, entered_by INTEGER, "
        "enter_reason TEXT NOT NULL, left_at DATETIME, left_by INTEGER, "
        "leave_reason TEXT, title_snapshot TEXT, state_id_snapshot INTEGER, "
        "status_name_snapshot TEXT, owner_id_snapshot INTEGER, "
        "operation_log_id INTEGER, migrated INTEGER NOT NULL DEFAULT 0)"
    ))


def test_work_pool_backfill_is_idempotent_and_reports_terminal_pool_anomalies():
    migration = _migration_module()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as bind:
        _create_schema(bind)
        bind.execute(sa.text("INSERT INTO projects VALUES (1, 10)"))
        bind.execute(sa.text(
            "INSERT INTO workflow_states VALUES (1, 'start'), (2, 'terminal')"
        ))
        bind.execute(sa.text(
            "INSERT INTO tasks VALUES "
            "(101, 1, NULL, 1, 0), "
            "(102, 1, 20, 1, 0), "
            "(103, 1, 10, 2, 0), "
            "(104, 1, NULL, 2, 0), "
            "(105, 1, NULL, 1, 1)"
        ))
        bind.execute(sa.text(
            "INSERT INTO bugs VALUES "
            "(201, 1, NULL, 1, 0), "
            "(202, 1, 20, 1, 0), "
            "(203, 1, 10, 2, 0)"
        ))
        bind.execute(sa.text(
            "INSERT INTO requirements VALUES (301, 1, 10, 2, 0)"
        ))

        first = migration._backfill_project_work_pool_items(bind)
        second = migration._backfill_project_work_pool_items(bind)

        task_rows = bind.execute(sa.text(
            "SELECT id, iteration_id FROM tasks ORDER BY id"
        )).all()
        bug_rows = bind.execute(sa.text(
            "SELECT id, iteration_id FROM bugs ORDER BY id"
        )).all()
        history_rows = bind.execute(sa.text(
            "SELECT object_type, object_id, iteration_id, enter_reason, migrated "
            "FROM work_item_iteration_history ORDER BY object_type, object_id"
        )).all()

    assert migration.revision == "20260806_002"
    assert migration.down_revision == "20260806_001"
    assert first == {
        "updated": {"task": 1, "bug": 1},
        "terminal_pool_anomalies": [
            {"object_type": "bug", "object_id": 203, "project_id": 1, "iteration_id": 10},
            {"object_type": "requirement", "object_id": 301, "project_id": 1, "iteration_id": 10},
            {"object_type": "task", "object_id": 103, "project_id": 1, "iteration_id": 10},
        ],
    }
    assert second == {
        "updated": {"task": 0, "bug": 0},
        "terminal_pool_anomalies": first["terminal_pool_anomalies"],
    }
    assert task_rows == [(101, 10), (102, 20), (103, 10), (104, None), (105, None)]
    assert bug_rows == [(201, 10), (202, 20), (203, 10)]
    assert history_rows == [
        ("bug", 201, 10, "project_work_pool_backfill", 1),
        ("task", 101, 10, "project_work_pool_backfill", 1),
    ]
