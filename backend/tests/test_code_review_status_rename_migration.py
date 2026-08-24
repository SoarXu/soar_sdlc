import importlib.util
from pathlib import Path

import sqlalchemy as sa


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "20260824_002_rename_review_states_to_code_review.py"
)


def test_review_state_rename_migration_is_scoped_to_work_items():
    assert MIGRATION_PATH.exists()
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'revision = "20260824_002"' in source
    assert 'down_revision = "20260824_001"' in source
    assert "UPDATE workflow_states" in source
    assert "requirement" in source
    assert "task" in source
    assert "bug" in source
    assert "待评审" in source
    assert "Code Review" in source


def test_review_state_rename_migration_updates_only_legacy_work_item_states(monkeypatch):
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    definitions = sa.Table(
        "workflow_definitions",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("object_type", sa.String, nullable=False),
    )
    states = sa.Table(
        "workflow_states",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("definition_id", sa.Integer, nullable=False),
        sa.Column("status_name", sa.String, nullable=False),
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(definitions.insert(), [
            {"id": 1, "object_type": "requirement"},
            {"id": 2, "object_type": "task"},
            {"id": 3, "object_type": "bug"},
            {"id": 4, "object_type": "project"},
        ])
        connection.execute(states.insert(), [
            {"id": 11, "definition_id": 1, "status_name": "待评审"},
            {"id": 12, "definition_id": 2, "status_name": "待评审"},
            {"id": 13, "definition_id": 3, "status_name": "待评审"},
            {"id": 14, "definition_id": 4, "status_name": "待评审"},
            {"id": 15, "definition_id": 1, "status_name": "Code Review"},
            {"id": 16, "definition_id": 1, "status_name": "处理中"},
        ])
        monkeypatch.setattr(migration, "op", _Operations(connection))

        migration.upgrade()
        migration.upgrade()

        assert connection.execute(
            sa.select(states.c.id, states.c.status_name).order_by(states.c.id)
        ).all() == [
            (11, "Code Review"),
            (12, "Code Review"),
            (13, "Code Review"),
            (14, "待评审"),
            (15, "Code Review"),
            (16, "处理中"),
        ]

        migration.downgrade()

        assert connection.execute(
            sa.select(states.c.id, states.c.status_name).order_by(states.c.id)
        ).all() == [
            (11, "Code Review"),
            (12, "Code Review"),
            (13, "Code Review"),
            (14, "待评审"),
            (15, "Code Review"),
            (16, "处理中"),
        ]


def _load_migration():
    spec = importlib.util.spec_from_file_location("code_review_status_rename_migration", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _Operations:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, statement):
        self.connection.execute(statement)
