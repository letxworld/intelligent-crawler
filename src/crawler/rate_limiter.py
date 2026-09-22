"""Rate limiter: per-host + global token bucket."""

from __future__ import annotations

import asyncio
import time
from urllib.parse import urlparse


class TokenBucket:
    """Simple token-bucket rate limiter."""

    def __init__(self, rate: float, burst: int | None = None) -> None:
        self.rate = rate  # tokens per second
        self.burst = burst or max(1, int(rate))
        self.tokens = float(self.burst)
        self.last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last = now
            if self.tokens < 1.0:
                wait = (1.0 - self.tokens) / self.rate
                await asyncio.sleep(wait)
                self.last = time.monotonic()
                self.tokens = 0.0
            else:
                self.tokens -= 1.0


class RateLimiter:
    """Combined global and per-host rate limiter."""

    def __init__(self, global_rate: float, per_host_rate: float | None = None) -> None:
        self.global_bucket = TokenBucket(global_rate)
        self.per_host_rate = per_host_rate or global_rate
        self._host_buckets: dict[str, TokenBucket] = {}
        self._host_lock = asyncio.Lock()

    async def acquire(self, url: str) -> None:
        host = urlparse(url).hostname or "unknown"
        await self.global_bucket.acquire()
        async with self._host_lock:
            bucket = self._host_buckets.get(host)
            if bucket is None:
                bucket = TokenBucket(self.per_host_rate)
                self._host_buckets[host] = bucket
        await bucket.acquire()
