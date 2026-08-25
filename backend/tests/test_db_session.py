from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

from app.db import session
from app.db.session import engine


def test_mysql_engine_checks_pooled_connections_before_use():
    if not engine.url.drivername.startswith("mysql"):
        return

    assert getattr(engine.pool, "_pre_ping", False) is True


def test_query_metrics_scope_counts_database_work_without_sql_content():
    scope = getattr(session, "query_metrics_scope", None)
    assert callable(scope), "query_metrics_scope is required"

    with scope() as metrics:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    assert metrics.query_count >= 1
    assert metrics.database_time_ms >= 0
    assert not hasattr(metrics, "statements")


def test_query_metrics_scope_counts_failed_database_work():
    with session.query_metrics_scope() as metrics:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT * FROM table_that_does_not_exist_for_metrics"))
        except DatabaseError:
            pass

    assert metrics.query_count == 1
    assert metrics.database_time_ms >= 0
