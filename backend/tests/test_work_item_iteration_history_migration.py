from pathlib import Path

from app.db.session import Base


ROOT = Path(__file__).parents[2]


def test_history_table_is_covered_by_metadata_init_sql_and_standalone_migration():
    table = Base.metadata.tables["work_item_iteration_history"]
    assert {"object_type", "object_id", "iteration_id", "operation_log_id", "migrated"} <= set(table.columns.keys())
    assert {index.name for index in table.indexes} >= {"idx_wiih_object", "idx_wiih_iteration"}
    migration = (ROOT / "backend/alembic/versions/20260722_003_work_item_iteration_history.py").read_text(encoding="utf-8")
    init_sql = (ROOT / "docs/database/init_mysql.sql").read_text(encoding="utf-8")
    assert 'revision: str = "20260722_003"' in migration
    assert 'down_revision: Union[str, None] = "20260722_002"' in migration
    assert "op.create_table(\"work_item_iteration_history\"" in migration
    assert "existing_columns" in migration
    assert '"idx_wiih_object"' in migration
    assert "CREATE TABLE IF NOT EXISTS work_item_iteration_history" in init_sql
