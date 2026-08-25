from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from time import perf_counter

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine_options = {"connect_args": connect_args}
if settings.database_url.startswith("mysql"):
    engine_options.update({"pool_pre_ping": True, "pool_recycle": 1800})

engine = create_engine(settings.database_url, **engine_options)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@dataclass
class QueryMetrics:
    query_count: int = 0
    database_time_ms: float = 0.0


_query_metrics: ContextVar[QueryMetrics | None] = ContextVar("query_metrics", default=None)


@contextmanager
def query_metrics_scope():
    metrics = QueryMetrics()
    token = _query_metrics.set(metrics)
    try:
        yield metrics
    finally:
        _query_metrics.reset(token)


@event.listens_for(engine, "before_cursor_execute")
def _start_query_timer(_conn, _cursor, _statement, _parameters, context, _executemany):
    context._soar_query_started_at = perf_counter()


@event.listens_for(engine, "after_cursor_execute")
def _record_query_metrics(_conn, _cursor, _statement, _parameters, context, _executemany):
    _finish_query_metrics(context)


@event.listens_for(engine, "handle_error")
def _record_failed_query_metrics(exception_context):
    _finish_query_metrics(exception_context.execution_context)


def _finish_query_metrics(context):
    metrics = _query_metrics.get()
    started_at = getattr(context, "_soar_query_started_at", None)
    if metrics is None or started_at is None or getattr(context, "_soar_query_recorded", False):
        return
    context._soar_query_recorded = True
    metrics.query_count += 1
    metrics.database_time_ms += (perf_counter() - started_at) * 1000


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
