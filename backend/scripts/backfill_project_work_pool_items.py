"""Idempotently backfill unallocated tasks and Bugs into project work pools."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import engine


def _migration_module():
    path = (
        BACKEND_ROOT
        / "alembic"
        / "versions"
        / "20260806_002_backfill_project_work_pool_items.py"
    )
    spec = importlib.util.spec_from_file_location("project_work_pool_backfill", path)
    if not spec or not spec.loader:
        raise RuntimeError(f"Cannot load migration: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    migration = _migration_module()
    with engine.begin() as connection:
        report = migration._backfill_project_work_pool_items(connection)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if report["terminal_pool_anomalies"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
