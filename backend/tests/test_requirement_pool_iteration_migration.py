import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.db import schema as runtime_schema
from app.models.iteration import Iteration
from app.models.project import Project
from app.models.requirement import Requirement
from app.views.iteration_view import IterationCreate, IterationRead, IterationUpdate
from app.views.project_view import ProjectCreate, ProjectRead, ProjectUpdate
from app.views.requirement_view import RequirementCreate, RequirementRead, RequirementUpdate


MIGRATION_PATH = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "20260728_001_project_requirement_pool_iterations.py"
)


def _migration_module():
    spec = importlib.util.spec_from_file_location(
        "project_requirement_pool_iterations",
        MIGRATION_PATH,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_requirement_pool_columns_are_registered_in_model_metadata():
    assert Iteration.__table__.c.is_requirement_pool.nullable is False
    assert Project.__table__.c.requirement_pool_iteration_id.nullable is True
    assert Project.__table__.c.requirement_pool_iteration_id.unique is True
    assert Requirement.__table__.c.iteration_id.nullable is False

    pool_fk = next(iter(Project.__table__.c.requirement_pool_iteration_id.foreign_keys))
    requirement_fk = next(iter(Requirement.__table__.c.iteration_id.foreign_keys))
    assert pool_fk.target_fullname == "iterations.id"
    assert pool_fk.ondelete == "RESTRICT"
    assert pool_fk.use_alter is True
    assert requirement_fk.target_fullname == "iterations.id"
    assert requirement_fk.ondelete == "RESTRICT"


def test_system_pool_identity_is_read_only_in_api_models():
    assert "is_requirement_pool" in IterationRead.model_fields
    assert "is_requirement_pool" not in IterationCreate.model_fields
    assert "is_requirement_pool" not in IterationUpdate.model_fields

    assert "requirement_pool_iteration_id" in ProjectRead.model_fields
    assert "requirement_pool_iteration_id" not in ProjectCreate.model_fields
    assert "requirement_pool_iteration_id" not in ProjectUpdate.model_fields

    assert RequirementCreate.model_fields["iteration_id"].annotation == int | None
    assert RequirementUpdate.model_fields["iteration_id"].annotation == int | None
    assert RequirementRead.model_fields["iteration_id"].annotation is int


def test_migration_revision_follows_business_component_routing_head():
    migration = _migration_module()

    assert migration.revision == "20260728_001"
    assert migration.down_revision == "20260727_001"


class _UpgradeOperationCapture:
    def __init__(self):
        self.columns = []

    def get_bind(self):
        return object()

    def add_column(self, table_name, column):
        self.columns.append((table_name, column))


def test_migration_adds_signed_project_pool_pointer(monkeypatch):
    migration = _migration_module()
    operations = _UpgradeOperationCapture()
    monkeypatch.setattr(migration, "op", operations)
    monkeypatch.setattr(migration, "_columns", lambda bind, table_name: set())
    monkeypatch.setattr(
        migration,
        "_resolve_default_iteration_workflow",
        lambda bind: (9, 90),
    )
    monkeypatch.setattr(migration, "_create_project_requirement_pools", lambda *args: None)
    monkeypatch.setattr(migration, "_backfill_requirement_iterations", lambda bind: None)
    monkeypatch.setattr(migration, "_audit_or_raise", lambda bind: None)
    monkeypatch.setattr(migration, "_add_constraints", lambda bind: None)

    migration.upgrade()

    pointer = next(
        column
        for table_name, column in operations.columns
        if table_name == "projects" and column.name == "requirement_pool_iteration_id"
    )
    assert type(pointer.type) is sa.BigInteger
    assert getattr(pointer.type, "unsigned", False) is False


class _ConstraintOperationCapture:
    def __init__(self):
        self.events = []

    def create_unique_constraint(self, name, table_name, columns):
        self.events.append(("unique", table_name, name, columns))

    def create_foreign_key(
        self,
        name,
        source_table,
        target_table,
        source_columns,
        target_columns,
        **kwargs,
    ):
        self.events.append(("foreign_key", source_table, name, source_columns))

    def alter_column(self, table_name, column_name, **kwargs):
        self.events.append(("alter", table_name, column_name, kwargs))

    def drop_constraint(self, name, table_name, **kwargs):
        self.events.append(("drop_constraint", table_name, name, kwargs))

    def drop_column(self, table_name, column_name):
        self.events.append(("drop_column", table_name, column_name))


def test_mysql_tightens_signed_requirement_iteration_before_adding_fk(monkeypatch):
    migration = _migration_module()
    operations = _ConstraintOperationCapture()
    bind = SimpleNamespace(dialect=SimpleNamespace(name="mysql"))
    monkeypatch.setattr(migration, "op", operations)
    monkeypatch.setattr(migration, "_unique_constraint_names", lambda *args: set())
    monkeypatch.setattr(migration, "_foreign_key_names", lambda *args: set())

    migration._add_constraints(bind)

    requirement_alter_index = next(
        index
        for index, event in enumerate(operations.events)
        if event[:3] == ("alter", "requirements", "iteration_id")
    )
    requirement_fk_index = next(
        index
        for index, event in enumerate(operations.events)
        if event[:3] == ("foreign_key", "requirements", migration._REQUIREMENT_ITERATION_FK)
    )
    alter_kwargs = operations.events[requirement_alter_index][3]
    assert requirement_alter_index < requirement_fk_index
    assert type(alter_kwargs["existing_type"]) is sa.BigInteger
    assert getattr(alter_kwargs["existing_type"], "unsigned", False) is False
    assert alter_kwargs["nullable"] is False


def test_mysql_downgrade_drops_requirement_fk_before_widening_nullable(monkeypatch):
    migration = _migration_module()
    operations = _ConstraintOperationCapture()
    bind = SimpleNamespace(
        dialect=SimpleNamespace(name="mysql"),
        execute=lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(migration, "op", operations)
    monkeypatch.setattr(
        migration,
        "_foreign_key_names",
        lambda bind, table_name: {
            "requirements": {migration._REQUIREMENT_ITERATION_FK},
            "projects": {migration._PROJECT_POOL_FK},
        }[table_name],
    )
    monkeypatch.setattr(
        migration,
        "_unique_constraint_names",
        lambda *args: {migration._PROJECT_POOL_UNIQUE},
    )
    monkeypatch.setattr(migration, "_remove_pool_rows", lambda bind: None)

    migration._drop_constraints_and_columns(bind)

    requirement_fk_drop_index = next(
        index
        for index, event in enumerate(operations.events)
        if event[:3] == (
            "drop_constraint",
            "requirements",
            migration._REQUIREMENT_ITERATION_FK,
        )
    )
    requirement_alter_index = next(
        index
        for index, event in enumerate(operations.events)
        if event[:3] == ("alter", "requirements", "iteration_id")
    )
    assert requirement_fk_drop_index < requirement_alter_index


def test_runtime_schema_adds_only_pool_identity_columns_with_signed_pointer(monkeypatch):
    calls = []
    engine = object()
    monkeypatch.setattr(
        runtime_schema,
        "_ensure_column",
        lambda *args: calls.append(args),
    )

    runtime_schema._ensure_requirement_pool_identity_columns(engine)

    assert [(table, column) for _, table, column, *_ in calls] == [
        ("iterations", "is_requirement_pool"),
        ("projects", "requirement_pool_iteration_id"),
    ]
    ddl_by_column = {column: ddl for _, _, column, ddl, *_ in calls}
    assert "TINYINT(1) NOT NULL DEFAULT 0" in ddl_by_column["is_requirement_pool"]
    pointer_ddl = ddl_by_column["requirement_pool_iteration_id"]
    assert " BIGINT NULL " in pointer_ddl
    assert "UNSIGNED" not in pointer_ddl
    assert "requirements" not in " ".join(ddl_by_column.values())


def test_runtime_schema_invokes_pool_identity_column_guard():
    source = (Path(__file__).parents[1] / "app" / "db" / "schema.py").read_text(
        encoding="utf-8"
    )
    runtime_schema_body = source.split("def ensure_runtime_schema", maxsplit=1)[1]

    assert "_ensure_requirement_pool_identity_columns(engine)" in runtime_schema_body


def test_migration_has_deterministic_integrity_audit():
    migration = _migration_module()
    issues = [
        {"issue": "null_requirement_iteration", "ids": [7]},
        {"issue": "missing_pool_reference", "ids": [9, 2, 9]},
    ]

    assert migration._format_audit_issues(issues) == (
        "Requirement pool migration audit failed: "
        "missing_pool_reference=2,9; null_requirement_iteration=7"
    )


def _create_audit_schema(bind):
    bind.execute(sa.text(
        "CREATE TABLE projects ("
        "id INTEGER PRIMARY KEY, requirement_pool_iteration_id INTEGER)"
    ))
    bind.execute(sa.text(
        "CREATE TABLE iterations ("
        "id INTEGER PRIMARY KEY, is_requirement_pool INTEGER NOT NULL)"
    ))
    bind.execute(sa.text(
        "CREATE TABLE iteration_projects ("
        "id INTEGER PRIMARY KEY, iteration_id INTEGER NOT NULL, project_id INTEGER NOT NULL)"
    ))
    bind.execute(sa.text(
        "CREATE TABLE requirements ("
        "id INTEGER PRIMARY KEY, iteration_id INTEGER)"
    ))


def test_migration_audit_covers_every_pool_integrity_failure():
    migration = _migration_module()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as bind:
        _create_audit_schema(bind)
        bind.execute(sa.text(
            "INSERT INTO projects (id, requirement_pool_iteration_id) VALUES "
            "(1, NULL), (2, 20), (3, 30)"
        ))
        bind.execute(sa.text(
            "INSERT INTO iterations (id, is_requirement_pool) VALUES (20, 0), (30, 1)"
        ))
        bind.execute(sa.text(
            "INSERT INTO iteration_projects (id, iteration_id, project_id) VALUES (1, 30, 99)"
        ))
        bind.execute(sa.text(
            "INSERT INTO requirements (id, iteration_id) VALUES (50, NULL), (51, 999)"
        ))

        issues = migration._collect_audit_issues(bind)

    assert issues == [
        {"issue": "dangling_requirement_iteration", "ids": [51]},
        {"issue": "missing_pool_reference", "ids": [1]},
        {"issue": "null_requirement_iteration", "ids": [50]},
        {"issue": "pool_scope_mismatch", "ids": [3]},
        {"issue": "wrong_pool_flag", "ids": [2]},
    ]


def _create_workflow_schema(bind):
    bind.execute(sa.text(
        "CREATE TABLE workflow_definitions ("
        "id INTEGER PRIMARY KEY, object_type TEXT NOT NULL, scope_type TEXT NOT NULL, "
        "is_default_template INTEGER NOT NULL, enabled INTEGER NOT NULL, initial_state_id INTEGER)"
    ))
    bind.execute(sa.text(
        "CREATE TABLE workflow_states ("
        "id INTEGER PRIMARY KEY, definition_id INTEGER NOT NULL, enabled INTEGER NOT NULL)"
    ))


def test_migration_resolves_latest_valid_default_iteration_workflow():
    migration = _migration_module()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as bind:
        _create_workflow_schema(bind)
        bind.execute(sa.text(
            "INSERT INTO workflow_definitions VALUES "
            "(8, 'iteration', 'system', 1, 1, 80), "
            "(9, 'iteration', 'system', 1, 1, 90)"
        ))
        bind.execute(sa.text(
            "INSERT INTO workflow_states VALUES (80, 8, 1), (90, 9, 1)"
        ))

        assert migration._resolve_default_iteration_workflow(bind) == (9, 90)


def test_migration_skips_newer_default_with_invalid_initial_state():
    migration = _migration_module()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as bind:
        _create_workflow_schema(bind)
        bind.execute(sa.text(
            "INSERT INTO workflow_definitions VALUES "
            "(8, 'iteration', 'system', 1, 1, 80), "
            "(9, 'iteration', 'system', 1, 1, 90)"
        ))
        bind.execute(sa.text(
            "INSERT INTO workflow_states VALUES (80, 8, 1), (90, 9, 0)"
        ))

        assert migration._resolve_default_iteration_workflow(bind) == (8, 80)


@pytest.mark.parametrize(
    "state_values",
    [
        "",
        "(90, 8, 1)",
        "(90, 9, 0)",
    ],
)
def test_migration_rejects_missing_or_invalid_initial_state(state_values):
    migration = _migration_module()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as bind:
        _create_workflow_schema(bind)
        bind.execute(sa.text(
            "INSERT INTO workflow_definitions VALUES "
            "(9, 'iteration', 'system', 1, 1, 90)"
        ))
        if state_values:
            bind.execute(sa.text(f"INSERT INTO workflow_states VALUES {state_values}"))

        with pytest.raises(RuntimeError, match="default system iteration workflow 9.*initial state 90"):
            migration._resolve_default_iteration_workflow(bind)


def _create_pool_backfill_schema(bind):
    bind.execute(sa.text(
        "CREATE TABLE projects ("
        "id INTEGER PRIMARY KEY, deleted INTEGER NOT NULL, delete_time TEXT, "
        "requirement_pool_iteration_id INTEGER)"
    ))
    bind.execute(sa.text(
        "CREATE TABLE iterations ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, owner_id INTEGER, "
        "start_date DATE, end_date DATE, actual_start_date DATE, actual_end_date DATE, "
        "is_requirement_pool INTEGER NOT NULL, workflow_definition_id INTEGER NOT NULL, "
        "current_state_id INTEGER NOT NULL, lifecycle_phase TEXT NOT NULL, goal TEXT, "
        "creator_id INTEGER, updater_id INTEGER, deleted INTEGER NOT NULL, delete_time TEXT)"
    ))
    bind.execute(sa.text(
        "CREATE TABLE iteration_projects ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, iteration_id INTEGER NOT NULL, project_id INTEGER NOT NULL)"
    ))
    bind.execute(sa.text(
        "CREATE TABLE requirements ("
        "id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL, iteration_id INTEGER)"
    ))


def test_pool_backfill_is_restart_safe_and_preserves_soft_delete_semantics():
    migration = _migration_module()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as bind:
        _create_pool_backfill_schema(bind)
        bind.execute(sa.text(
            "INSERT INTO projects VALUES "
            "(1, 0, NULL, NULL), (2, 1, '2026-07-01 12:00:00', NULL)"
        ))
        bind.execute(sa.text(
            "INSERT INTO requirements VALUES (101, 1, NULL), (102, 2, NULL)"
        ))

        migration._create_project_requirement_pools(bind, 9, 90)
        migration._create_project_requirement_pools(bind, 9, 90)
        migration._backfill_requirement_iterations(bind)

        pools = bind.execute(sa.text(
            "SELECT id, name, lifecycle_phase, deleted, delete_time "
            "FROM iterations ORDER BY id"
        )).mappings().all()
        memberships = bind.execute(sa.text(
            "SELECT iteration_id, project_id FROM iteration_projects ORDER BY project_id"
        )).all()
        project_refs = bind.execute(sa.text(
            "SELECT id, requirement_pool_iteration_id FROM projects ORDER BY id"
        )).all()
        requirement_refs = bind.execute(sa.text(
            "SELECT id, iteration_id FROM requirements ORDER BY id"
        )).all()

        assert migration._collect_audit_issues(bind) == []

    assert len(pools) == 2
    assert [(row["name"], row["lifecycle_phase"], row["deleted"]) for row in pools] == [
        ("需求池", "development", 0),
        ("需求池", "development", 1),
    ]
    assert pools[0]["delete_time"] is None
    assert str(pools[1]["delete_time"]) == "2026-07-01 12:00:00"
    assert memberships == [(1, 1), (2, 2)]
    assert project_refs == [(1, 1), (2, 2)]
    assert requirement_refs == [(101, 1), (102, 2)]


def test_downgrade_cleanup_removes_only_pool_iterations_and_memberships():
    migration = _migration_module()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as bind:
        bind.execute(sa.text(
            "CREATE TABLE iterations (id INTEGER PRIMARY KEY, is_requirement_pool INTEGER NOT NULL)"
        ))
        bind.execute(sa.text(
            "CREATE TABLE iteration_projects ("
            "id INTEGER PRIMARY KEY, iteration_id INTEGER NOT NULL, project_id INTEGER NOT NULL)"
        ))
        bind.execute(sa.text(
            "INSERT INTO iterations VALUES (10, 1), (20, 0)"
        ))
        bind.execute(sa.text(
            "INSERT INTO iteration_projects VALUES (1, 10, 1), (2, 20, 1)"
        ))

        migration._remove_pool_rows(bind)

        assert bind.execute(sa.text("SELECT id FROM iterations ORDER BY id")).scalars().all() == [20]
        assert bind.execute(sa.text(
            "SELECT iteration_id FROM iteration_projects ORDER BY id"
        )).scalars().all() == [20]


def test_sqlite_upgrade_and_downgrade_apply_the_complete_schema_contract(monkeypatch):
    migration = _migration_module()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as bind:
        _create_workflow_schema(bind)
        bind.execute(sa.text(
            "CREATE TABLE projects ("
            "id INTEGER PRIMARY KEY, deleted INTEGER NOT NULL, delete_time TEXT)"
        ))
        bind.execute(sa.text(
            "CREATE TABLE iterations ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, owner_id INTEGER, "
            "start_date DATE, end_date DATE, actual_start_date DATE, actual_end_date DATE, "
            "workflow_definition_id INTEGER NOT NULL, current_state_id INTEGER NOT NULL, "
            "lifecycle_phase TEXT NOT NULL, goal TEXT, creator_id INTEGER, updater_id INTEGER, "
            "deleted INTEGER NOT NULL, delete_time TEXT)"
        ))
        bind.execute(sa.text(
            "CREATE TABLE iteration_projects ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, iteration_id INTEGER NOT NULL, project_id INTEGER NOT NULL)"
        ))
        bind.execute(sa.text(
            "CREATE TABLE requirements ("
            "id INTEGER PRIMARY KEY, project_id INTEGER NOT NULL, iteration_id INTEGER)"
        ))
        bind.execute(sa.text(
            "INSERT INTO workflow_definitions VALUES "
            "(9, 'iteration', 'system', 1, 1, 90)"
        ))
        bind.execute(sa.text("INSERT INTO workflow_states VALUES (90, 9, 1)"))
        bind.execute(sa.text("INSERT INTO projects VALUES (1, 0, NULL)"))
        bind.execute(sa.text("INSERT INTO requirements VALUES (101, 1, NULL)"))
        monkeypatch.setattr(
            migration,
            "op",
            Operations(MigrationContext.configure(bind)),
        )

        migration.upgrade()

        inspector = sa.inspect(bind)
        project_columns = {item["name"]: item for item in inspector.get_columns("projects")}
        iteration_columns = {item["name"]: item for item in inspector.get_columns("iterations")}
        requirement_columns = {item["name"]: item for item in inspector.get_columns("requirements")}
        assert project_columns["requirement_pool_iteration_id"]["nullable"] is True
        assert iteration_columns["is_requirement_pool"]["nullable"] is False
        assert requirement_columns["iteration_id"]["nullable"] is False
        assert bind.execute(sa.text(
            "SELECT COUNT(*) FROM requirements WHERE iteration_id IS NULL"
        )).scalar_one() == 0

        migration.downgrade()

        inspector = sa.inspect(bind)
        assert "requirement_pool_iteration_id" not in {
            item["name"] for item in inspector.get_columns("projects")
        }
        assert "is_requirement_pool" not in {
            item["name"] for item in inspector.get_columns("iterations")
        }
        assert next(
            item for item in inspector.get_columns("requirements") if item["name"] == "iteration_id"
        )["nullable"] is True
        assert bind.execute(sa.text("SELECT iteration_id FROM requirements")).scalar_one() is None
