"""Unit tests for the rate limiter."""

from __future__ import annotations

import asyncio
import time

import pytest

from crawler.rate_limiter import RateLimiter, TokenBucket


@pytest.mark.asyncio
async def test_token_bucket_acquire() -> None:
    bucket = TokenBucket(rate=10.0)
    start = time.monotonic()
    await bucket.acquire()
    elapsed = time.monotonic() - start
    # First acquire should be immediate (token available).
    assert elapsed < 0.05


@pytest.mark.asyncio
async def test_token_bucket_throttle() -> None:
    bucket = TokenBucket(rate=2.0, burst=1)
    await bucket.acquire()
    start = time.monotonic()
    await bucket.acquire()
    elapsed = time.monotonic() - start
    # Should take at least 0.5s for 2/sec with 0 tokens.
    assert elapsed >= 0.4


@pytest.mark.asyncio
async def test_rate_limiter_global_and_per_host() -> None:
    limiter = RateLimiter(global_rate=2.0, per_host_rate=2.0)
    # 3 sequential acquires on same host: first two are burst, third must wait.
    start = time.monotonic()
    await limiter.acquire("https://example.com/a")
    await limiter.acquire("https://example.com/b")
    await limiter.acquire("https://example.com/c")
    elapsed = time.monotonic() - start
    # Third acquire should have been throttled ~0.5s.
    assert elapsed >= 0.4


@pytest.mark.asyncio
async def test_rate_limiter_independent_hosts() -> None:
    limiter = RateLimiter(global_rate=100.0, per_host_rate=100.0)
    start = time.monotonic()
    tasks = [
        limiter.acquire("https://a.example.com/x"),
        limiter.acquire("https://b.example.com/y"),
    ]
    await asyncio.gather(*tasks)
    elapsed = time.monotonic() - start
    # Different hosts, high rate — should be fast.
    assert elapsed < 0.5
