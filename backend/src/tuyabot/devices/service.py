"""Async bridge for blocking Tuya I/O, with a hard timeout."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any

logger = logging.getLogger(__name__)

_executor: ThreadPoolExecutor | None = None
_threads = 4
_default_timeout = 25.0


def configure(threads: int, timeout_seconds: float) -> None:
    """Called at startup and when the settings change."""
    global _executor, _threads, _default_timeout
    _default_timeout = float(timeout_seconds)
    if _threads != int(threads) and _executor is not None:
        _executor.shutdown(wait=False)
        _executor = None
    _threads = int(threads)


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=_threads, thread_name_prefix="tuya")
    return _executor


async def run_tuya(
    fn: Callable[..., dict[str, Any]],
    *args: Any,
    timeout: float | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run blocking Tuya work off the event loop.

    On timeout the caller gets `success: False` rather than an exception: the
    request must fail fast, not hang, and the device thread finishes on its own.
    """
    loop = asyncio.get_running_loop()
    limit = _default_timeout if timeout is None else timeout
    future = loop.run_in_executor(_get_executor(), partial(fn, *args, **kwargs))
    try:
        return await asyncio.wait_for(future, timeout=limit)
    except TimeoutError:
        logger.warning("[TUYA] panggilan melewati batas %.1fs", limit)
        return {"success": False, "message": f"Timeout {limit:.0f}s saat menghubungi perangkat"}


def shutdown(wait: bool = True) -> None:
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=wait)
        _executor = None
