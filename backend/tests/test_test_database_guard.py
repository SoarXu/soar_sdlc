import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url

import app.models  # noqa: F401
from app.db.session import Base
from app.testing import database as test_database
from app.testing.database import prepare_test_database_from_environment, validate_test_database_urls


SOURCE_URL = "mysql+pymysql://user:password@localhost:3306/soar_sdlc"


def test_test_database_must_not_match_application_database():
    with pytest.raises(RuntimeError, match="must differ"):
        validate_test_database_urls(SOURCE_URL, SOURCE_URL)


def test_test_database_rejects_case_and_host_aliases_for_same_database_name():
    with pytest.raises(RuntimeError, match="must differ"):
        validate_test_database_urls(
            "mysql+pymysql://user:password@localhost:3306/SOAR_SDLC_TEST",
            "mysql+pymysql://user:password@127.0.0.1:3306/soar_sdlc_test",
        )


def test_test_database_name_must_end_with_test():
    with pytest.raises(RuntimeError, match="must end with '_test'"):
        validate_test_database_urls(
            SOURCE_URL,
            "mysql+pymysql://user:password@localhost:3306/another_database",
        )


def test_dedicated_mysql_test_database_is_accepted():
    source, target = validate_test_database_urls(
        SOURCE_URL,
        "mysql+pymysql://user:password@localhost:3306/soar_sdlc_test",
    )

    assert source.database == "soar_sdlc"
    assert target.database == "soar_sdlc_test"


def test_sqlalchemy_metadata_creates_a_fresh_mysql_schema():
    configured_url = make_url(os.environ["TEST_DATABASE_URL"])
    schema_database = f"soar_schema_{uuid4().hex}_test"
    schema_url = configured_url.set(database=schema_database)
    admin_engine = create_engine(configured_url.set(database=None))
    schema_engine = create_engine(schema_url)
    created = False
    try:
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(
                f"CREATE DATABASE `{schema_database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            created = True
        Base.metadata.create_all(schema_engine)
        assert set(Base.metadata.tables) <= set(inspect(schema_engine).get_table_names())
    finally:
        schema_engine.dispose()
        if created:
            with admin_engine.connect() as connection:
                connection.exec_driver_sql(f"DROP DATABASE `{schema_database}`")
        admin_engine.dispose()


def test_test_database_preparation_is_idempotent_in_one_process(monkeypatch):
    def unexpected_recreation(*_args):
        raise AssertionError("test database was recreated twice")

    monkeypatch.setattr(test_database, "recreate_mysql_test_database", unexpected_recreation)

    _source, target = prepare_test_database_from_environment(os.environ.copy())

    assert target.database.endswith("_test")
