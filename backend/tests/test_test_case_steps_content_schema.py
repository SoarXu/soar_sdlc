from pathlib import Path

from sqlalchemy import Text
from sqlalchemy.dialects import mysql

from app.models import test_case as test_case_models
from app.views import test_case_view as test_case_views


def test_rich_text_columns_use_mysql_mediumtext_and_remain_nullable():
    for name in ("precondition", "steps_content", "expected_result"):
        column = test_case_models.TestCase.__table__.c[name]
        assert isinstance(column.type, Text)
        assert column.type.compile(dialect=mysql.dialect()) == "MEDIUMTEXT"
        assert column.nullable is True
    assert "steps_content" in test_case_views.TestCaseCreate.model_fields
    assert "steps_content" in test_case_views.TestCaseUpdate.model_fields
    assert "steps_content" in test_case_views.TestCaseRead.model_fields


def test_steps_content_is_bootstrapped_and_has_an_alembic_migration():
    root = Path(__file__).resolve().parents[1]
    schema_source = (root / "app/db/schema.py").read_text(encoding="utf-8")
    migration_source = (root / "alembic/versions/20260811_001_test_case_steps_content.py").read_text(encoding="utf-8")
    assert '_ensure_column(engine, "test_cases", "steps_content"' in schema_source
    assert "ALTER TABLE test_cases ADD COLUMN steps_content MEDIUMTEXT NULL" in schema_source
    assert 'revision: str = "20260811_001"' in migration_source
    assert 'down_revision: Union[str, None] = "20260810_001"' in migration_source
    assert "mysql.MEDIUMTEXT()" in migration_source
    assert 'op.alter_column("test_cases", "precondition"' in migration_source
    assert 'op.alter_column("test_cases", "expected_result"' in migration_source
