from app.db.session import engine


def test_mysql_engine_checks_pooled_connections_before_use():
    if not engine.url.drivername.startswith("mysql"):
        return

    assert getattr(engine.pool, "_pre_ping", False) is True
