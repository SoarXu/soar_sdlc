import importlib.util
from pathlib import Path

import sqlalchemy as sa


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "20260824_003_rename_workflow_add_information_to_comment.py"
)


def test_workflow_comment_action_rename_migration_has_expected_revision_chain():
    assert MIGRATION_PATH.exists()
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'revision = "20260824_003"' in source
    assert 'down_revision = "20260824_002"' in source
    assert "UPDATE workflow_transitions" in source
    assert "add_information" in source
    assert "补充信息" in source
    assert "评论" in source
    assert "requirement" in source
    assert "task" in source
    assert "bug" in source


def test_workflow_comment_action_rename_migration_is_scoped_and_idempotent(monkeypatch):
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    definitions = sa.Table(
        "workflow_definitions",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("object_type", sa.String, nullable=False),
    )
    transitions = sa.Table(
        "workflow_transitions",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("definition_id", sa.Integer, nullable=False),
        sa.Column("from_state_id", sa.Integer, nullable=False),
        sa.Column("action_key", sa.String, nullable=False),
        sa.Column("action_name", sa.String, nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False),
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(definitions.insert(), [
            {"id": 1, "object_type": "requirement"},
            {"id": 2, "object_type": "task"},
            {"id": 3, "object_type": "bug"},
            {"id": 4, "object_type": "project"},
        ])
        connection.execute(transitions.insert(), [
            {"id": 11, "definition_id": 1, "from_state_id": 101, "action_key": "add_information", "action_name": "补充信息", "enabled": True},
            {"id": 12, "definition_id": 2, "from_state_id": 201, "action_key": "add_information", "action_name": "补充信息", "enabled": True},
            {"id": 13, "definition_id": 3, "from_state_id": 301, "action_key": "add_information", "action_name": "补充信息", "enabled": True},
            {"id": 14, "definition_id": 4, "from_state_id": 401, "action_key": "add_information", "action_name": "补充信息", "enabled": True},
            {"id": 15, "definition_id": 1, "from_state_id": 102, "action_key": "complete", "action_name": "补充信息", "enabled": True},
            {"id": 16, "definition_id": 1, "from_state_id": 103, "action_key": "add_information", "action_name": "评论", "enabled": True},
            {"id": 17, "definition_id": 1, "from_state_id": 104, "action_key": "add_information", "action_name": "补充信息", "enabled": False},
            {"id": 18, "definition_id": 1, "from_state_id": 104, "action_key": "custom_comment", "action_name": "评论", "enabled": True},
            {"id": 19, "definition_id": 1, "from_state_id": 105, "action_key": "add_information", "action_name": "补充信息", "enabled": True},
            {"id": 20, "definition_id": 1, "from_state_id": 105, "action_key": "custom_comment", "action_name": "评论", "enabled": True},
        ])
        monkeypatch.setattr(migration, "op", _Operations(connection))

        migration.upgrade()
        migration.upgrade()

        assert connection.execute(
            sa.select(transitions.c.id, transitions.c.action_name).order_by(transitions.c.id)
        ).all() == [
            (11, "评论"),
            (12, "评论"),
            (13, "评论"),
            (14, "补充信息"),
            (15, "补充信息"),
            (16, "评论"),
            (17, "评论"),
            (18, "评论"),
            (19, "补充信息"),
            (20, "评论"),
        ]

        migration.downgrade()

        assert connection.execute(
            sa.select(transitions.c.id, transitions.c.action_name).order_by(transitions.c.id)
        ).all() == [
            (11, "评论"),
            (12, "评论"),
            (13, "评论"),
            (14, "补充信息"),
            (15, "补充信息"),
            (16, "评论"),
            (17, "评论"),
            (18, "评论"),
            (19, "补充信息"),
            (20, "评论"),
        ]


def _load_migration():
    spec = importlib.util.spec_from_file_location("workflow_comment_action_rename_migration", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _Operations:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, statement):
        return self.connection.execute(statement)

    def get_bind(self):
        return self.connection
