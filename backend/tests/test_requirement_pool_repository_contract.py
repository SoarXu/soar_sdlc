from pathlib import Path
import importlib.util
import re

from app.models.iteration import Iteration
from app.models.project import Project
from app.views.iteration_view import IterationRead
from app.views.project_view import ProjectRead


REPOSITORY_ROOT = Path(__file__).parents[2]
DICTIONARY_PATH = REPOSITORY_ROOT / "docs/database/2026-06-09-intellective-bio-sdlc-data-dictionary-mysql.md"
BOOTSTRAP_SQL_PATH = REPOSITORY_ROOT / "docs/database/init_mysql.sql"
MIGRATION_PATH = (
    REPOSITORY_ROOT
    / "backend/alembic/versions/20260811_002_remove_requirement_pool_iterations.py"
)
TEST_INFRASTRUCTURE_PATH = REPOSITORY_ROOT / "backend/tests/conftest.py"


def _migration_module():
    spec = importlib.util.spec_from_file_location("remove_requirement_pool_iterations", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _table_definition(sql: str, table_name: str) -> str:
    match = re.search(
        rf"CREATE TABLE IF NOT EXISTS {table_name} \((.*?)\) ENGINE=InnoDB",
        sql,
        flags=re.DOTALL,
    )
    assert match, f"{table_name} bootstrap definition is missing"
    return match.group(1)


def test_real_iteration_assignment_removes_pool_identity_from_runtime_contracts():
    assert "requirement_pool_iteration_id" not in Project.__table__.c
    assert "is_requirement_pool" not in Iteration.__table__.c
    assert "requirement_pool_iteration_id" not in ProjectRead.model_fields
    assert "is_requirement_pool" not in IterationRead.model_fields


def test_bootstrap_and_dictionary_remove_requirement_pool_identity():
    dictionary = DICTIONARY_PATH.read_text(encoding="utf-8")
    sql = BOOTSTRAP_SQL_PATH.read_text(encoding="utf-8")

    assert "requirement_pool_iteration_id" not in dictionary
    assert "is_requirement_pool" not in dictionary
    assert "requirement_pool_iteration_id" not in _table_definition(sql, "projects")
    assert "is_requirement_pool" not in _table_definition(sql, "iterations")
    assert "iteration_id BIGINT UNSIGNED NOT NULL" in _table_definition(sql, "requirements")


def test_removal_migration_moves_items_before_dropping_pool_columns():
    source = MIGRATION_PATH.read_text(encoding="utf-8")

    assert "state.category IN ('start', 'normal', 'in_progress')" in source
    assert "CASE WHEN state.category IN ('normal', 'in_progress') THEN 0 ELSE 1 END" in source
    assert "_create_target_iteration" in source
    assert "_move_pool_items" in source
    assert 'batch.drop_column("requirement_pool_iteration_id")' in source
    assert 'batch.drop_column("is_requirement_pool")' in source


def test_removal_migration_locates_constraints_by_exact_columns(monkeypatch):
    migration = _migration_module()

    class Inspector:
        def get_foreign_keys(self, _table_name):
            return [
                {"name": "fk_mysql_auto_42", "constrained_columns": ["requirement_pool_iteration_id"]},
                {"name": "fk_requirement_pool_unrelated", "constrained_columns": ["owner_id"]},
            ]

        def get_unique_constraints(self, _table_name):
            return [
                {"name": "uq_mysql_auto_17", "column_names": ["requirement_pool_iteration_id"]},
                {"name": "uq_requirement_pool_unrelated", "column_names": ["name"]},
            ]

    monkeypatch.setattr(migration.sa, "inspect", lambda _bind: Inspector())

    assert migration._constraint_names_for_columns(
        object(), "projects", "foreign_key", ("requirement_pool_iteration_id",)
    ) == ["fk_mysql_auto_42"]
    assert migration._constraint_names_for_columns(
        object(), "projects", "unique", ("requirement_pool_iteration_id",)
    ) == ["uq_mysql_auto_17"]


def test_post_migration_test_cleanup_does_not_reference_removed_pool_columns():
    source = TEST_INFRASTRUCTURE_PATH.read_text(encoding="utf-8")

    assert "requirement_pool_iteration_id" not in source
    assert "is_requirement_pool" not in source
