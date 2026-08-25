import importlib.util
from pathlib import Path

import sqlalchemy as sa


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "20260824_004_remove_bug_unassigned_ownership_actions.py"
)


def test_bug_unassigned_ownership_action_removal_migration_has_expected_revision_chain():
    assert MIGRATION_PATH.exists()
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert 'revision = "20260824_004"' in source
    assert 'down_revision = "20260824_003"' in source
    assert "DELETE FROM workflow_transitions" in source
    assert "DELETE FROM business_component_transition_routes" in source
    assert "DELETE FROM workflow_transition_roles" in source
    assert "unassigned" in source
    assert "transfer" in source
    assert "change_handler" in source


def test_bug_unassigned_ownership_action_removal_migration_deletes_all_bug_unassigned_ownership_actions(monkeypatch):
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
        sa.Column("state_role", sa.String),
    )
    transitions = sa.Table(
        "workflow_transitions",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("definition_id", sa.Integer, nullable=False),
        sa.Column("from_state_id", sa.Integer, nullable=False),
        sa.Column("action_key", sa.String, nullable=False),
    )
    transition_roles = sa.Table(
        "workflow_transition_roles",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("transition_id", sa.Integer, nullable=False),
    )
    component_routes = sa.Table(
        "business_component_transition_routes",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "transition_id",
            sa.Integer,
            sa.ForeignKey("workflow_transitions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(sa.text("PRAGMA foreign_keys = ON"))
        connection.execute(definitions.insert(), [
            {"id": 1, "object_type": "bug"},
            {"id": 2, "object_type": "bug"},
            {"id": 3, "object_type": "bug"},
            {"id": 4, "object_type": "task"},
        ])
        connection.execute(states.insert(), [
            {"id": 11, "definition_id": 1, "state_role": "unassigned"},
            {"id": 12, "definition_id": 2, "state_role": "unassigned"},
            {"id": 13, "definition_id": 3, "state_role": "unassigned"},
            {"id": 14, "definition_id": 1, "state_role": "waiting_iteration"},
            {"id": 15, "definition_id": 1, "state_role": "active_work"},
            {"id": 16, "definition_id": 4, "state_role": "unassigned"},
        ])
        connection.execute(transitions.insert(), [
            {"id": 101, "definition_id": 1, "from_state_id": 11, "action_key": "transfer"},
            {"id": 102, "definition_id": 2, "from_state_id": 12, "action_key": "change_handler"},
            {"id": 103, "definition_id": 3, "from_state_id": 13, "action_key": "transfer"},
            {"id": 104, "definition_id": 1, "from_state_id": 11, "action_key": "assign"},
            {"id": 105, "definition_id": 1, "from_state_id": 14, "action_key": "transfer"},
            {"id": 106, "definition_id": 1, "from_state_id": 15, "action_key": "change_handler"},
            {"id": 107, "definition_id": 4, "from_state_id": 16, "action_key": "transfer"},
        ])
        connection.execute(transition_roles.insert(), [
            {"id": 1001, "transition_id": 101},
            {"id": 1002, "transition_id": 102},
            {"id": 1003, "transition_id": 104},
            {"id": 1004, "transition_id": 999},
        ])
        connection.execute(component_routes.insert(), [
            {"id": 2001, "transition_id": 101},
            {"id": 2002, "transition_id": 102},
        ])
        monkeypatch.setattr(migration, "op", _Operations(connection))

        migration.upgrade()
        migration.upgrade()

        assert connection.execute(
            sa.select(transitions.c.id).order_by(transitions.c.id)
        ).scalars().all() == [104, 105, 106, 107]
        assert connection.execute(
            sa.select(transition_roles.c.id).order_by(transition_roles.c.id)
        ).scalars().all() == [1003]
        assert connection.execute(
            sa.select(component_routes.c.id).order_by(component_routes.c.id)
        ).scalars().all() == []


def test_bug_unassigned_ownership_action_removal_migration_cleans_orphaned_role_refs_without_targets(monkeypatch):
    migration = _load_migration()
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    definitions = sa.Table(
        "workflow_definitions",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("object_type", sa.String, nullable=False),
    )
    sa.Table(
        "workflow_states",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("definition_id", sa.Integer, nullable=False),
        sa.Column("state_role", sa.String),
    )
    sa.Table(
        "workflow_transitions",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("definition_id", sa.Integer, nullable=False),
        sa.Column("from_state_id", sa.Integer, nullable=False),
        sa.Column("action_key", sa.String, nullable=False),
    )
    transition_roles = sa.Table(
        "workflow_transition_roles",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("transition_id", sa.Integer, nullable=False),
    )
    metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(definitions.insert(), [{"id": 1, "object_type": "bug"}])
        connection.execute(transition_roles.insert(), [{"id": 1001, "transition_id": 999}])
        monkeypatch.setattr(migration, "op", _Operations(connection))

        migration.upgrade()

        assert connection.execute(sa.select(transition_roles.c.id)).scalars().all() == []


def _load_migration():
    spec = importlib.util.spec_from_file_location("bug_unassigned_ownership_action_recovery_migration", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _Operations:
    def __init__(self, connection):
        self.connection = connection

    def get_bind(self):
        return self.connection
