"""Acceptance tests for active program-name uniqueness by parent scope."""

import ast
import importlib.util
import inspect
import re
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.db import schema
from app.db.session import SessionLocal
from app.models.program import Program
from app.services import program_service


def _unique_name(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def _create_program(client: TestClient, name: str, *, parent_id: int | None = None) -> dict:
    payload = {"name": name}
    if parent_id is not None:
        payload["parent_id"] = parent_id
    response = client.post("/api/v1/programs", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def _assert_program_name_conflict(response) -> None:
    assert response.status_code == 422
    assert response.json()["detail"] == "Program name already exists in this parent scope"


def test_rejects_duplicate_top_level_program_name(client: TestClient):
    name = _unique_name("top-level-name")
    _create_program(client, name)

    duplicate = client.post("/api/v1/programs", json={"name": name})

    _assert_program_name_conflict(duplicate)


def test_rejects_duplicate_sibling_program_name(client: TestClient):
    parent = _create_program(client, _unique_name("sibling-parent"))
    name = _unique_name("sibling-name")
    _create_program(client, name, parent_id=parent["id"])

    duplicate = client.post("/api/v1/programs", json={"name": name, "parent_id": parent["id"]})

    _assert_program_name_conflict(duplicate)


def test_allows_same_program_name_under_different_parents(client: TestClient):
    first_parent = _create_program(client, _unique_name("first-parent"))
    second_parent = _create_program(client, _unique_name("second-parent"))
    name = _unique_name("shared-child-name")

    _create_program(client, name, parent_id=first_parent["id"])
    second_child = client.post("/api/v1/programs", json={"name": name, "parent_id": second_parent["id"]})

    assert second_child.status_code == 200, second_child.text


def test_trims_program_names_before_persisting(client: TestClient):
    name = _unique_name("trimmed-name")

    created = _create_program(client, f"  {name}  ")

    assert created["name"] == name


def test_rejects_whitespace_only_program_name(client: TestClient):
    rejected = client.post("/api/v1/programs", json={"name": " \t "})

    assert rejected.status_code == 422
    assert "name" in rejected.json()["detail"].lower()


def test_rejects_null_program_name_on_update(client: TestClient):
    program = _create_program(client, _unique_name("null-update-name"))

    rejected = client.patch(f"/api/v1/programs/{program['id']}", json={"name": None})

    assert rejected.status_code == 422
    assert "name" in rejected.json()["detail"].lower()


def test_allows_updating_program_with_its_own_normalized_name(client: TestClient):
    name = _unique_name("same-normalized-update")
    program = _create_program(client, name)

    updated = client.patch(f"/api/v1/programs/{program['id']}", json={"name": f"  {name.upper()}  "})

    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == name.upper()


def test_trims_program_name_on_update(client: TestClient):
    program = _create_program(client, _unique_name("trim-update-name"))
    name = _unique_name("trimmed-update-name")

    updated = client.patch(f"/api/v1/programs/{program['id']}", json={"name": f"  {name}  "})

    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == name


def test_rejects_whitespace_only_program_name_on_update(client: TestClient):
    program = _create_program(client, _unique_name("blank-update-name"))

    rejected = client.patch(f"/api/v1/programs/{program['id']}", json={"name": " \t "})

    assert rejected.status_code == 422
    assert "name" in rejected.json()["detail"].lower()


def test_rejects_case_only_and_whitespace_only_program_name_variants(client: TestClient):
    name = _unique_name("case-sensitive-name")
    _create_program(client, name)

    case_only = client.post("/api/v1/programs", json={"name": name.upper()})
    whitespace_only = client.post("/api/v1/programs", json={"name": f"  {name}  "})

    _assert_program_name_conflict(case_only)
    _assert_program_name_conflict(whitespace_only)


def test_allows_reusing_program_name_after_soft_delete(client: TestClient):
    name = _unique_name("reusable-after-delete")
    original = _create_program(client, name)

    deleted = client.delete(f"/api/v1/programs/{original['id']}")
    replacement = client.post("/api/v1/programs", json={"name": name})

    assert deleted.status_code == 204, deleted.text
    assert replacement.status_code == 200, replacement.text


def test_rejects_rename_that_conflicts_in_its_parent_scope(client: TestClient):
    parent = _create_program(client, _unique_name("rename-parent"))
    existing = _create_program(client, _unique_name("existing-name"), parent_id=parent["id"])
    renamed = _create_program(client, _unique_name("renamed-name"), parent_id=parent["id"])

    conflict = client.patch(f"/api/v1/programs/{renamed['id']}", json={"name": existing["name"]})

    _assert_program_name_conflict(conflict)


def test_rejects_move_that_conflicts_in_target_parent_scope(client: TestClient):
    source_parent = _create_program(client, _unique_name("move-source-parent"))
    target_parent = _create_program(client, _unique_name("move-target-parent"))
    name = _unique_name("move-conflict-name")
    moving = _create_program(client, name, parent_id=source_parent["id"])
    _create_program(client, name, parent_id=target_parent["id"])

    conflict = client.patch(f"/api/v1/programs/{moving['id']}", json={"parent_id": target_parent["id"]})

    _assert_program_name_conflict(conflict)


def test_rejects_moving_legacy_whitespace_name_into_normalized_duplicate_scope(client: TestClient):
    source_parent = _create_program(client, _unique_name("legacy-source-parent"))
    target_parent = _create_program(client, _unique_name("legacy-target-parent"))
    name = _unique_name("legacy-whitespace-name")
    _create_program(client, name, parent_id=target_parent["id"])
    db = SessionLocal()
    try:
        legacy_program = Program(name=f"  {name}  ", parent_id=source_parent["id"])
        db.add(legacy_program)
        db.commit()
        db.refresh(legacy_program)
        legacy_program_id = legacy_program.id
    finally:
        db.close()

    conflict = client.patch(f"/api/v1/programs/{legacy_program_id}", json={"parent_id": target_parent["id"]})

    _assert_program_name_conflict(conflict)
    db = SessionLocal()
    try:
        assert db.get(Program, legacy_program_id).parent_id == source_parent["id"]
    finally:
        db.close()


def test_rejects_non_ascii_case_only_sibling_program_name(client: TestClient):
    parent = _create_program(client, _unique_name("non-ascii-parent"))
    suffix = _unique_name("non-ascii-name")
    _create_program(client, f"\u00c4-{suffix}", parent_id=parent["id"])

    duplicate = client.post("/api/v1/programs", json={"name": f"\u00e4-{suffix}", "parent_id": parent["id"]})

    _assert_program_name_conflict(duplicate)


def test_mysql_schema_declares_active_scope_name_unique_constraint():
    source_tree = ast.parse(inspect.getsource(schema))
    ddl_literals = "\n".join(
        node.value
        for node in ast.walk(source_tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    )

    assert re.search(
        r"ALTER TABLE programs\s+ADD COLUMN program_name_scope\s+"
        r"BIGINT(?:\s+UNSIGNED)?\s+GENERATED ALWAYS AS\s*\(\s*"
        r"CASE WHEN deleted\s*=\s*0 THEN COALESCE\(parent_id,\s*0\) ELSE NULL END\s*\)",
        ddl_literals,
        flags=re.DOTALL,
    )
    assert re.search(
        r"ALTER TABLE programs\s+ADD COLUMN program_name_normalized\s+"
        r"VARCHAR\(150\)\s+GENERATED ALWAYS AS",
        ddl_literals,
        flags=re.DOTALL,
    )
    assert "LOWER(REGEXP_REPLACE(name, '^[[:space:]]+|[[:space:]]+$', ''))" in ddl_literals
    assert re.search(
        r"CREATE UNIQUE INDEX\s+\w+\s+ON programs\s*"
        r"\(program_name_scope,\s*program_name_normalized\)",
        ddl_literals,
        flags=re.DOTALL,
    )


class _SchemaConnection:
    def __init__(self, statements: list[str], rows=None):
        self.statements = statements
        self.rows = rows or []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, statement):
        self.statements.append(str(statement))
        return SimpleNamespace(all=lambda: self.rows)


class _SchemaEngine:
    def __init__(self, *, dialect_name: str = "mysql", rows=None):
        self.dialect = SimpleNamespace(name=dialect_name)
        self.statements: list[str] = []
        self.rows = rows or []

    def begin(self):
        return _SchemaConnection(self.statements, self.rows)

    def execute(self, statement):
        self.statements.append(str(statement))
        return SimpleNamespace(all=lambda: self.rows)


class _ProgramsInspector:
    def __init__(self, *, columns, indexes):
        self.columns = columns
        self.indexes = indexes

    def get_table_names(self):
        return ["programs"]

    def get_columns(self, table_name):
        assert table_name == "programs"
        return [{"name": column} for column in self.columns]

    def get_indexes(self, table_name):
        assert table_name == "programs"
        return self.indexes


def test_mysql_runtime_schema_installs_only_program_name_generated_columns_and_unique_index(monkeypatch):
    engine = _SchemaEngine()
    monkeypatch.setattr(
        schema,
        "inspect",
        lambda inspected_engine: _ProgramsInspector(
            columns={"id", "parent_id", "name", "deleted"}, indexes=[]
        ),
    )

    schema._ensure_program_name_uniqueness_schema(engine)

    ddl = "\n".join(engine.statements)
    assert "ALTER TABLE programs ADD COLUMN program_name_scope" in ddl
    assert "ALTER TABLE programs ADD COLUMN program_name_normalized" in ddl
    assert "CREATE UNIQUE INDEX uk_program_name_scope_normalized ON programs" in ddl
    assert "workflow" not in ddl.lower()


def test_mysql_runtime_schema_is_idempotent_when_program_name_contract_already_exists(monkeypatch):
    engine = _SchemaEngine()
    monkeypatch.setattr(
        schema,
        "inspect",
        lambda inspected_engine: _ProgramsInspector(
            columns={
                "id",
                "parent_id",
                "name",
                "deleted",
                "program_name_scope",
                "program_name_normalized",
            },
            indexes=[
                {
                    "name": "uk_program_name_scope_normalized",
                    "column_names": ["program_name_scope", "program_name_normalized"],
                    "unique": True,
                }
            ],
        ),
    )

    schema._ensure_program_name_uniqueness_schema(engine)

    assert engine.statements == []


def test_mysql_runtime_schema_rejects_incompatible_canonical_program_name_index(monkeypatch):
    engine = _SchemaEngine()
    monkeypatch.setattr(
        schema,
        "inspect",
        lambda inspected_engine: _ProgramsInspector(
            columns={"id", "parent_id", "name", "deleted", "program_name_scope", "program_name_normalized"},
            indexes=[
                {
                    "name": "uk_program_name_scope_normalized",
                    "column_names": ["program_name_scope"],
                    "unique": True,
                }
            ],
        ),
    )

    with pytest.raises(RuntimeError, match="incompatible definition"):
        schema._ensure_program_name_uniqueness_schema(engine)


def test_mysql_runtime_schema_rejects_alternate_program_name_index(monkeypatch):
    engine = _SchemaEngine()
    monkeypatch.setattr(
        schema,
        "inspect",
        lambda inspected_engine: _ProgramsInspector(
            columns={"id", "parent_id", "name", "deleted", "program_name_scope", "program_name_normalized"},
            indexes=[
                {
                    "name": "another_program_name_index",
                    "column_names": ["program_name_scope", "program_name_normalized"],
                    "unique": True,
                }
            ],
        ),
    )

    with pytest.raises(RuntimeError, match="not the required canonical index"):
        schema._ensure_program_name_uniqueness_schema(engine)


def test_mysql_runtime_schema_refuses_legacy_duplicate_active_program_names(monkeypatch):
    engine = _SchemaEngine(rows=[(0, "duplicate", "14,19", "Example | example")])
    monkeypatch.setattr(
        schema,
        "inspect",
        lambda inspected_engine: _ProgramsInspector(
            columns={"id", "parent_id", "name", "deleted"}, indexes=[]
        ),
    )

    with pytest.raises(RuntimeError) as raised:
        schema._ensure_program_name_uniqueness_schema(engine)

    message = str(raised.value)
    assert "scope=0" in message
    assert "ids=[14,19]" in message
    assert "names=[Example | example]" in message
    assert all("ADD COLUMN" not in statement for statement in engine.statements)


def test_runtime_schema_wires_program_name_constraint():
    source = inspect.getsource(schema.ensure_runtime_schema)

    assert "_ensure_program_name_uniqueness_schema(engine)" in source


def test_runtime_schema_skips_program_name_constraint_for_sqlite(monkeypatch):
    engine = _SchemaEngine(dialect_name="sqlite")
    monkeypatch.setattr(
        schema,
        "inspect",
        lambda inspected_engine: (_ for _ in ()).throw(AssertionError("SQLite must skip MySQL DDL")),
    )

    schema._ensure_program_name_uniqueness_schema(engine)

    assert engine.statements == []


def _load_program_name_migration(revision: str = "20260730_001_program_name_uniqueness"):
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / f"{revision}.py"
    )
    spec = importlib.util.spec_from_file_location("program_name_uniqueness_migration", migration_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_program_name_migration_upgrade_and_downgrade_add_and_remove_mysql_contract(monkeypatch):
    migration = _load_program_name_migration()
    statements: list[str] = []
    bind = _SchemaEngine()
    inspector = _ProgramsInspector(
        columns={"id", "parent_id", "name", "deleted"}, indexes=[]
    )
    monkeypatch.setattr(
        migration,
        "op",
        SimpleNamespace(
            get_bind=lambda: bind,
            execute=lambda statement: statements.append(str(statement)),
        ),
    )
    monkeypatch.setattr(migration.sa, "inspect", lambda inspected_bind: inspector)

    migration.upgrade()
    inspector.columns.update({"program_name_scope", "program_name_normalized"})
    inspector.indexes.append(
        {
            "name": "uk_program_name_scope_normalized",
            "column_names": ["program_name_scope", "program_name_normalized"],
            "unique": True,
        }
    )
    migration.downgrade()

    ddl = "\n".join(statements)
    assert "ALTER TABLE programs ADD COLUMN program_name_scope" in ddl
    assert "ALTER TABLE programs ADD COLUMN program_name_normalized" in ddl
    assert "CREATE UNIQUE INDEX uk_program_name_scope_normalized ON programs" in ddl
    assert "DROP INDEX uk_program_name_scope_normalized ON programs" in ddl
    assert "DROP COLUMN program_name_normalized" in ddl
    assert "DROP COLUMN program_name_scope" in ddl
    assert "REGEXP_REPLACE(name, '^[[:space:]]+|[[:space:]]+$', '')" in ddl


def test_program_name_migration_rejects_alternate_index_that_would_block_downgrade(monkeypatch):
    migration = _load_program_name_migration()
    bind = _SchemaEngine()
    inspector = _ProgramsInspector(
        columns={"id", "parent_id", "name", "deleted", "program_name_scope", "program_name_normalized"},
        indexes=[
            {
                "name": "alternate_program_name_index",
                "column_names": ["program_name_scope", "program_name_normalized"],
                "unique": True,
            }
        ],
    )
    monkeypatch.setattr(migration, "op", SimpleNamespace(get_bind=lambda: bind, execute=lambda statement: None))
    monkeypatch.setattr(migration.sa, "inspect", lambda inspected_bind: inspector)

    with pytest.raises(RuntimeError, match="not the required canonical index"):
        migration.upgrade()


def test_program_name_whitespace_migration_rebuilds_canonical_contract(monkeypatch):
    migration = _load_program_name_migration("20260730_002_fix_program_name_whitespace_normalization")
    statements: list[str] = []
    bind = _SchemaEngine()
    inspector = _ProgramsInspector(
        columns={"id", "parent_id", "name", "deleted", "program_name_scope", "program_name_normalized"},
        indexes=[
            {
                "name": "uk_program_name_scope_normalized",
                "column_names": ["program_name_scope", "program_name_normalized"],
                "unique": True,
            }
        ],
    )
    monkeypatch.setattr(
        migration,
        "op",
        SimpleNamespace(get_bind=lambda: bind, execute=lambda statement: statements.append(str(statement))),
    )
    monkeypatch.setattr(migration.sa, "inspect", lambda inspected_bind: inspector)

    migration.upgrade()

    ddl = "\n".join(statements)
    assert "DROP INDEX uk_program_name_scope_normalized ON programs" in ddl
    assert "DROP COLUMN program_name_normalized" in ddl
    assert "REGEXP_REPLACE(name, '^[[:space:]]+|[[:space:]]+$', '')" in ddl
    assert "CREATE UNIQUE INDEX uk_program_name_scope_normalized ON programs" in ddl


def test_mysql_program_name_lookup_uses_generated_index_columns_when_available(monkeypatch):
    statements: list[str] = []
    mysql_bind = SimpleNamespace(dialect=SimpleNamespace(name="mysql"))
    db = SimpleNamespace(
        get_bind=lambda: mysql_bind,
        execute=lambda statement, values: (
            statements.append(str(statement))
            or SimpleNamespace(scalar_one_or_none=lambda: 1)
        ),
    )
    monkeypatch.setattr(
        program_service,
        "inspect",
        lambda bind: _ProgramsInspector(
            columns={"program_name_scope", "program_name_normalized"},
            indexes=[
                {
                    "name": "uk_program_name_scope_normalized",
                    "column_names": ["program_name_scope", "program_name_normalized"],
                    "unique": True,
                }
            ],
        ),
    )

    try:
        program_service._require_unique_program_name(db, "Example", None)
    except Exception as exc:
        assert getattr(exc, "detail", None) == "Program name already exists in this parent scope"
    else:
        raise AssertionError("generated-column lookup must reject an existing active program")

    assert "program_name_scope" in statements[0]
    assert "program_name_normalized" in statements[0]
    assert "LOWER(REGEXP_REPLACE" in statements[0]


def test_only_program_name_unique_index_integrity_errors_map_to_domain_conflict():
    expected = IntegrityError(
        "INSERT INTO programs ...",
        {},
        Exception("Duplicate entry '0-example' for key 'UK_PROGRAM_NAME_SCOPE_NORMALIZED'"),
    )
    unrelated = IntegrityError(
        "INSERT INTO programs ...",
        {},
        Exception("Cannot add or update a child row: a foreign key constraint fails"),
    )

    assert program_service._is_program_name_unique_constraint_error(expected)
    assert not program_service._is_program_name_unique_constraint_error(unrelated)


def test_program_name_unique_index_integrity_error_becomes_domain_conflict():
    expected = IntegrityError(
        "INSERT INTO programs ...",
        {},
        Exception("Duplicate entry '0-example' for key 'uk_program_name_scope_normalized'"),
    )
    db = SimpleNamespace(
        commit=lambda: (_ for _ in ()).throw(expected),
        rollback=lambda: None,
    )

    with pytest.raises(HTTPException) as raised:
        program_service._commit_program_name_change(db)

    assert raised.value.status_code == 422
    assert raised.value.detail == "Program name already exists in this parent scope"
