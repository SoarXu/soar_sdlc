from contextlib import contextmanager
from typing import Callable, TypeVar

from sqlalchemy.orm import Session


T = TypeVar("T")
_CACHE_KEY = "workflow_runtime_batch_cache"
_MISSING = object()


@contextmanager
def workflow_runtime_batch_cache(db: Session):
    if not hasattr(db, "info"):
        yield
        return
    previous = db.info.get(_CACHE_KEY, _MISSING)
    db.info[_CACHE_KEY] = {}
    try:
        yield
    finally:
        if previous is _MISSING:
            db.info.pop(_CACHE_KEY, None)
        else:
            db.info[_CACHE_KEY] = previous


def cached_runtime_value(db: Session, namespace: str, key, loader: Callable[[], T]) -> T:
    cache = getattr(db, "info", {}).get(_CACHE_KEY)
    if cache is None:
        return loader()
    values = cache.setdefault(namespace, {})
    if key not in values:
        values[key] = loader()
    return values[key]


def prime_runtime_values(db: Session, namespace: str, values: dict) -> None:
    cache = getattr(db, "info", {}).get(_CACHE_KEY)
    if cache is not None:
        cache.setdefault(namespace, {}).update(values)
