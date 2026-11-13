"""Regression coverage for persisted custom workflow action identifiers."""
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa

from app.core.config import settings
from app.db.schema import _ensure_status_operation_action_capacity
from app.models.status_operation import StatusOperationLog
from app.models.workflow_definition import WorkflowTransition


class CustomWorkflowActionCapacityTests(unittest.TestCase):
    def test_operation_log_accepts_full_workflow_action_key(self):
        action = "custom_be9bfa325c464655b8f2692fac648e5c"
        capacity = StatusOperationLog.__table__.c.action.type.length
        self.assertGreaterEqual(capacity, len(action))
        self.assertGreaterEqual(capacity, WorkflowTransition.__table__.c.action_key.type.length)


@unittest.skipUnless(os.environ.get("WORKFLOW_CAPACITY_TEST_DATABASE_URL"), "Requires an isolated MySQL test database")
class CustomWorkflowActionMySQLTests(unittest.TestCase):
    def setUp(self):
        target = sa.engine.make_url(os.environ["WORKFLOW_CAPACITY_TEST_DATABASE_URL"])
        source = sa.engine.make_url(settings.database_url)
        self.assertTrue(target.database.endswith("_test"))
        self.assertNotEqual(target.database, source.database)
        self.engine = sa.create_engine(target)
        self.addCleanup(self.engine.dispose)
        with self.engine.begin() as connection:
            connection.exec_driver_sql("DROP TABLE IF EXISTS status_operation_log")
            connection.exec_driver_sql(
                "CREATE TABLE status_operation_log (id BIGINT PRIMARY KEY AUTO_INCREMENT, action VARCHAR(32) NOT NULL)"
            )
            connection.exec_driver_sql("INSERT INTO status_operation_log (action) VALUES ('start')")

    def test_migration_preserves_history_and_full_length_actions(self):
        migration_path = Path(__file__).parents[1] / "alembic/versions/20261113_001_expand_status_operation_action.py"
        spec = importlib.util.spec_from_file_location("expand_status_operation_action", migration_path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        custom_action = "custom_be9bfa325c464655b8f2692fac648e5c"
        with self.engine.begin() as connection:
            operations = Operations(MigrationContext.configure(connection))
            with patch.object(migration, "op", operations), patch.object(migration.context, "is_offline_mode", return_value=False):
                migration.upgrade()
                migration.upgrade()
                for action in (custom_action, "x" * 64):
                    connection.execute(sa.text("INSERT INTO status_operation_log (action) VALUES (:action)"), {"action": action})
                migration.downgrade()
            self.assertEqual(
                connection.execute(sa.text("SELECT action FROM status_operation_log ORDER BY id")).scalars().all(),
                ["start", custom_action, "x" * 64],
            )
            column = next(c for c in sa.inspect(connection).get_columns("status_operation_log") if c["name"] == "action")
            self.assertEqual(column["type"].length, 64)
            self.assertFalse(column["nullable"])

    def test_runtime_upgrade_is_repeatable_and_does_not_shrink_wider_columns(self):
        _ensure_status_operation_action_capacity(self.engine)
        _ensure_status_operation_action_capacity(self.engine)
        with self.engine.begin() as connection:
            connection.execute(sa.text("INSERT INTO status_operation_log (action) VALUES (:action)"), {"action": "x" * 64})
            connection.exec_driver_sql("ALTER TABLE status_operation_log MODIFY COLUMN action VARCHAR(128) NOT NULL")
        _ensure_status_operation_action_capacity(self.engine)
        with self.engine.connect() as connection:
            column = next(c for c in sa.inspect(connection).get_columns("status_operation_log") if c["name"] == "action")
            self.assertEqual(column["type"].length, 128)
            self.assertEqual(connection.execute(sa.text("SELECT action FROM status_operation_log ORDER BY id")).scalars().all(), ["start", "x" * 64])


if __name__ == "__main__":
    unittest.main()
