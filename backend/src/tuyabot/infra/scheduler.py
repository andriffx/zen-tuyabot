"""Single interval scheduler for all periodic work."""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Job:
    name: str
    interval: float
    func: Callable[[], Awaitable[Any] | Any]
    initial_delay: float = 0.0
    next_run: float = 0.0
    runs: int = 0
    failures: int = 0
    enabled: bool = True


class Scheduler:
    def __init__(self) -> None:
        self._jobs: list[Job] = []
        self._task: asyncio.Task | None = None
        self._stop: asyncio.Event | None = None

    @property
    def jobs(self) -> list[Job]:
        return list(self._jobs)

    def add_job(
        self, name: str, interval: float, func: Callable[[], Any], initial_delay: float = 0.0
    ) -> Job:
        if interval <= 0:
            raise ValueError(f"interval job '{name}' harus > 0")
        if any(job.name == name for job in self._jobs):
            raise ValueError(f"job '{name}' sudah terdaftar")
        job = Job(name=name, interval=float(interval), func=func, initial_delay=float(initial_delay))
        self._jobs.append(job)
        return job

    def get(self, name: str) -> Job | None:
        return next((job for job in self._jobs if job.name == name), None)

    def reschedule(self, name: str, interval: float) -> None:
        job = self.get(name)
        if job is None:
            raise KeyError(name)
        job.interval = float(interval)
        job.next_run = time.monotonic() + job.interval

    def set_enabled(self, name: str, enabled: bool) -> None:
        job = self.get(name)
        if job is not None:
            job.enabled = enabled

    def start(self) -> asyncio.Task:
        loop = asyncio.get_running_loop()
        now = loop.time()
        for job in self._jobs:
            job.next_run = now + job.initial_delay
        self._stop = asyncio.Event()
        self._task = loop.create_task(self._main(), name="scheduler")
        return self._task

    async def stop(self) -> None:
        if self._stop is not None:
            self._stop.set()
        task, self._task = self._task, None
        if task and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    async def run_due(self) -> None:
        loop = asyncio.get_running_loop()
        now = loop.time()
        for job in [job for job in self._jobs if job.enabled and job.next_run <= now]:
            await self._execute(job)
            job.next_run = loop.time() + job.interval

    async def _execute(self, job: Job) -> None:
        try:
            result = job.func()
            if inspect.isawaitable(result):
                await result
            job.runs += 1
        except asyncio.CancelledError:
            raise
        except Exception:
            job.failures += 1
            logger.exception("[SCHEDULER] job '%s' gagal", job.name)

    async def _main(self) -> None:
        loop = asyncio.get_running_loop()
        assert self._stop is not None
        logger.info(
            "Scheduler aktif: %s",
            ", ".join(f"{job.name}/{job.interval:g}s" for job in self._jobs) or "(tanpa job)",
        )
        try:
            while not self._stop.is_set():
                await self.run_due()
                active = [job.next_run for job in self._jobs if job.enabled]
                delay = min(active, default=loop.time() + 60) - loop.time()
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=max(0.05, delay))
                except TimeoutError:
                    continue
        except asyncio.CancelledError:
            logger.info("Scheduler dibatalkan (shutdown).")
            raise
