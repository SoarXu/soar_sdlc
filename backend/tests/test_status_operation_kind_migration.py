from pathlib import Path

from app.db.session import Base


REPOSITORY_ROOT = Path(__file__).parents[2]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"


def test_status_operation_kind_is_present_in_model_and_schema_assets():
    column = Base.metadata.tables["status_operation_log"].columns["operation_kind"]
    assert column.nullable is False
    assert str(column.server_default.arg) == "'state'"

    runtime_schema = (BACKEND_ROOT / "app/db/schema.py").read_text(encoding="utf-8")
    migration = (
        BACKEND_ROOT / "alembic/versions/20260722_002_status_operation_kind.py"
    ).read_text(encoding="utf-8")
    init_sql = (REPOSITORY_ROOT / "docs/database/init_mysql.sql").read_text(encoding="utf-8")

    for source in (runtime_schema, migration, init_sql):
        assert "operation_kind" in source
        assert "DEFAULT 'state'" in source or 'server_default="state"' in source
    assert "action LIKE 'iteration\\\\_%'" in runtime_schema
    assert "action LIKE 'iteration\\\\_%'" in migration
