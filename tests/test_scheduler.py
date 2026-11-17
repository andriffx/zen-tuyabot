"""Scheduler: interval handling and reschedule."""

import asyncio

import pytest

from tuyabot.infra.scheduler import Scheduler


def test_job_runs_and_counts():
    calls = {"n": 0}

    async def job():
        calls["n"] += 1

    async def scenario():
        scheduler = Scheduler()
        scheduler.add_job("demo", 0.01, job)
        await scheduler.run_due()
        scheduler.get("demo").next_run = 0
        await scheduler.run_due()

    asyncio.run(scenario())
    assert calls["n"] == 2


def test_reschedule_changes_interval():
    scheduler = Scheduler()
    scheduler.add_job("demo", 60, lambda: None)
    scheduler.reschedule("demo", 5)
    assert scheduler.get("demo").interval == 5


def test_disabled_job_does_not_run():
    calls = {"n": 0}

    async def job():
        calls["n"] += 1

    async def scenario():
        scheduler = Scheduler()
        scheduler.add_job("demo", 0.01, job, initial_delay=0)
        scheduler.set_enabled("demo", False)
        await scheduler.run_due()

    asyncio.run(scenario())
    assert calls["n"] == 0


def test_failing_job_is_counted_not_raised():
    def boom():
        raise RuntimeError("gagal")

    async def scenario():
        scheduler = Scheduler()
        scheduler.add_job("boom", 0.01, boom)
        await scheduler.run_due()

    asyncio.run(scenario())  # must not raise


def test_duplicate_job_rejected():
    scheduler = Scheduler()
    scheduler.add_job("x", 1, lambda: None)
    with pytest.raises(ValueError):
        scheduler.add_job("x", 1, lambda: None)


def test_zero_interval_rejected():
    with pytest.raises(ValueError):
        Scheduler().add_job("x", 0, lambda: None)
