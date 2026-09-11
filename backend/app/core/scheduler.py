import asyncio
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import datetime, time, timedelta
from typing import Any

from fastapi import FastAPI

from app.jobs.iteration_jobs import run_auto_start_due_iterations
from app.jobs.ldap_jobs import run_weekly_ldap_sync


JobFunc = Callable[[], Any]
logger = logging.getLogger("app.scheduler")


def scheduled_jobs() -> list[dict[str, Any]]:
    return [
        {
            "name": "auto_start_due_iterations",
            "hour": 3,
            "minute": 0,
            "func": run_auto_start_due_iterations,
        },
        {
            "name": "weekly_ldap_user_sync",
            "weekday": 6,
            "hour": 2,
            "minute": 0,
            "func": run_weekly_ldap_sync,
        },
    ]


@asynccontextmanager
async def scheduler_lifespan(app: FastAPI):
    tasks = [asyncio.create_task(_run_daily_job(job)) for job in scheduled_jobs()]
    app.state.scheduler_tasks = tasks
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


async def _run_daily_job(job: dict[str, Any]) -> None:
    while True:
        await asyncio.sleep(_seconds_until(job["hour"], job["minute"], weekday=job.get("weekday")))
        try:
            result = await asyncio.to_thread(job["func"])
            if asyncio.iscoroutine(result):
                await result
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.error("scheduled_job_failed", extra={"job_name": job["name"]})


def _seconds_until(
    hour: int,
    minute: int,
    now: datetime | None = None,
    weekday: int | None = None,
) -> float:
    current = now or datetime.now()
    target = datetime.combine(current.date(), time(hour=hour, minute=minute))
    if weekday is not None:
        target += timedelta(days=(weekday - current.weekday()) % 7)
        if target <= current:
            target += timedelta(days=7)
    elif target <= current:
        target += timedelta(days=1)
    return (target - current).total_seconds()
