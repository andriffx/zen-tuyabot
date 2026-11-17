"""Async bridge for blocking database work.

No route handler may call sqlite3 on the event loop. Everything goes through
`run_db`, which runs in a dedicated executor with a hard timeout.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any

DB_TIMEOUT_SECONDS = 15.0
_executor: ThreadPoolExecutor | None = None


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="db")
    return _executor


async def run_db(fn: Callable[..., Any], *args: Any, timeout: float = DB_TIMEOUT_SECONDS, **kwargs: Any) -> Any:
    loop = asyncio.get_running_loop()
    future = loop.run_in_executor(_get_executor(), partial(fn, *args, **kwargs))
    return await asyncio.wait_for(future, timeout=timeout)


def shutdown(wait: bool = True) -> None:
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=wait)
        _executor = None
