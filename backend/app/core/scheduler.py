import asyncio
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import datetime, time, timedelta
from typing import Any

from fastapi import FastAPI

from app.jobs.iteration_jobs import run_auto_start_due_iterations


JobFunc = Callable[[], Any]


def scheduled_jobs() -> list[dict[str, Any]]:
    return [
        {
            "name": "auto_start_due_iterations",
            "hour": 3,
            "minute": 0,
            "func": run_auto_start_due_iterations,
        }
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
        await asyncio.sleep(_seconds_until(job["hour"], job["minute"]))
        result = job["func"]()
        if asyncio.iscoroutine(result):
            await result


def _seconds_until(hour: int, minute: int, now: datetime | None = None) -> float:
    current = now or datetime.now()
    target = datetime.combine(current.date(), time(hour=hour, minute=minute))
    if target <= current:
        target += timedelta(days=1)
    return (target - current).total_seconds()
