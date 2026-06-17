from __future__ import annotations

import asyncio
import time


class RateLimiter:
    """Simple per-process rate limiter enforcing a minimum spacing between calls.

    Limits upstream calls to ``rate_per_sec`` requests/second. A value of 0
    disables limiting. Concurrent callers are serialised through a lock so the
    spacing holds across coroutines.
    """

    def __init__(self, rate_per_sec: float) -> None:
        self._min_interval = 1.0 / rate_per_sec if rate_per_sec > 0 else 0.0
        self._lock = asyncio.Lock()
        self._next_allowed = 0.0

    async def acquire(self) -> None:
        if self._min_interval <= 0:
            return
        async with self._lock:
            now = time.monotonic()
            wait = self._next_allowed - now
            if wait > 0:
                await asyncio.sleep(wait)
                now = time.monotonic()
            self._next_allowed = now + self._min_interval
