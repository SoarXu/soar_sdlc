import os
import re
from collections.abc import MutableMapping

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, make_url


TEST_DATABASE_URL_ENV = "TEST_DATABASE_URL"
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_$]+$")
_prepared_urls: tuple[URL, URL] | None = None


class _ApplicationDatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str


def validate_test_database_urls(source_url: str, test_url: str) -> tuple[URL, URL]:
    source = make_url(source_url)
    target = make_url(test_url)
    if not source.drivername.startswith("mysql") or not target.drivername.startswith("mysql"):
        raise RuntimeError("Application and test databases must both use MySQL")
    if not source.database or not target.database:
        raise RuntimeError("Application and test database URLs must include a database name")
    if target.database.casefold() == source.database.casefold():
        raise RuntimeError("Test database must differ from the application database")
    if not target.database.lower().endswith("_test"):
        raise RuntimeError("Test database name must end with '_test'")
    _quote_identifier(source.database)
    _quote_identifier(target.database)
    return source, target


def prepare_test_database_from_environment(
    environ: MutableMapping[str, str] | None = None,
) -> tuple[URL, URL]:
    global _prepared_urls
    environment = environ if environ is not None else os.environ
    test_url = environment.get(TEST_DATABASE_URL_ENV)
    if not test_url:
        raise RuntimeError(
            f"{TEST_DATABASE_URL_ENV} is required; pytest is not allowed to use the application database"
        )
    if _prepared_urls is not None and make_url(test_url) == _prepared_urls[1]:
        environment["DATABASE_URL"] = _prepared_urls[1].render_as_string(hide_password=False)
        return _prepared_urls

    source_url = _ApplicationDatabaseSettings().database_url
    source, target = validate_test_database_urls(source_url, test_url)
    recreate_mysql_test_database(target)
    environment["DATABASE_URL"] = target.render_as_string(hide_password=False)
    _prepared_urls = (source, target)
    return _prepared_urls


def recreate_mysql_test_database(target: URL) -> None:
    target_name = _quote_identifier(target.database)
    admin_engine = create_engine(target.set(database=None), pool_pre_ping=True)
    try:
        with admin_engine.connect() as connection:
            connection.exec_driver_sql(f"DROP DATABASE IF EXISTS {target_name}")
            connection.exec_driver_sql(
                f"CREATE DATABASE {target_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        admin_engine.dispose()


def _quote_identifier(value: str | None) -> str:
    if not value or not _SAFE_IDENTIFIER.fullmatch(value):
        raise RuntimeError(f"Unsafe MySQL identifier: {value!r}")
    return f"`{value}`"
