import asyncio
from datetime import datetime

import pytest

from app.core import scheduler
from app.core.scheduler import _run_daily_job, _seconds_until, scheduled_jobs


def test_scheduler_registers_iteration_auto_start_job_at_3am():
    jobs = scheduled_jobs()

    iteration_job = next(job for job in jobs if job["name"] == "auto_start_due_iterations")
    assert iteration_job["hour"] == 3
    assert iteration_job["minute"] == 0
    assert "weekday" not in iteration_job


def test_scheduler_registers_ldap_sync_for_sunday_at_2am():
    ldap_job = next(job for job in scheduled_jobs() if job["name"] == "weekly_ldap_user_sync")

    assert ldap_job["weekday"] == 6
    assert ldap_job["hour"] == 2
    assert ldap_job["minute"] == 0


def test_seconds_until_supports_weekly_and_preserves_daily_scheduling():
    monday = datetime(2026, 9, 7, 1, 0)
    sunday_after_run = datetime(2026, 9, 13, 3, 0)

    assert _seconds_until(3, 0, now=monday) == 2 * 60 * 60
    assert _seconds_until(2, 0, weekday=6, now=monday) == 6 * 24 * 60 * 60 + 60 * 60
    assert _seconds_until(2, 0, weekday=6, now=sunday_after_run) == 6 * 24 * 60 * 60 + 23 * 60 * 60


def test_scheduler_runs_sync_job_in_thread_and_awaits_coroutine_result(monkeypatch):
    calls = []
    sleep_count = 0

    async def fake_sleep(_seconds):
        nonlocal sleep_count
        sleep_count += 1
        if sleep_count > 1:
            raise asyncio.CancelledError()

    async def fake_to_thread(func):
        calls.append("to_thread")
        return func()

    async def returned_coroutine():
        calls.append("awaited")

    monkeypatch.setattr(scheduler.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(scheduler.asyncio, "to_thread", fake_to_thread)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(_run_daily_job({"name": "test_job", "hour": 0, "minute": 0, "func": lambda: returned_coroutine()}))

    assert calls == ["to_thread", "awaited"]


def test_scheduler_logs_failure_and_continues_with_next_run(monkeypatch, caplog):
    attempts = 0
    sleep_count = 0

    async def fake_sleep(_seconds):
        nonlocal sleep_count
        sleep_count += 1
        if sleep_count > 2:
            raise asyncio.CancelledError()

    async def fake_to_thread(func):
        return func()

    def flaky_job():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("sensitive backend detail")

    monkeypatch.setattr(scheduler.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(scheduler.asyncio, "to_thread", fake_to_thread)

    with caplog.at_level("ERROR", logger="app.scheduler"):
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(_run_daily_job({"name": "flaky_job", "hour": 0, "minute": 0, "func": flaky_job}))

    assert attempts == 2
    assert [record.message for record in caplog.records] == ["scheduled_job_failed"]
    assert caplog.records[0].job_name == "flaky_job"
    assert "sensitive backend detail" not in caplog.text
