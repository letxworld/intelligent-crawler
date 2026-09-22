"""Integration test: full pipeline with scope-check + rate limiter + fetcher."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from crawler.fetcher import ScopedFetcher
from crawler.rate_limiter import RateLimiter
from crawler.scope_config import ScopeConfig


@pytest.fixture
def config(tmp_path) -> ScopeConfig:
    """Return a test scope config."""
    return ScopeConfig(
        allowed_domains=["*.example.com"],
        excluded_paths=["/secret/*"],
        rate_limit=100.0,
        dry_run=False,
    )


@pytest.fixture
def fetcher(config: ScopeConfig) -> ScopedFetcher:
    rate_limiter = RateLimiter(global_rate=config.rate_limit)
    return ScopedFetcher(config=config, rate_limiter=rate_limiter)


@pytest.mark.asyncio
async def test_fetch_blocked_by_scope(fetcher: ScopedFetcher) -> None:
    """Out-of-scope URL should be blocked and return None."""
    resp = await fetcher.get("https://evil.com/page")
    assert resp is None


@pytest.mark.asyncio
async def test_fetch_excluded_path(fetcher: ScopedFetcher) -> None:
    """Excluded path should be blocked."""
    resp = await fetcher.get("https://app.example.com/secret/admin")
    assert resp is None


@pytest.mark.asyncio
async def test_fetch_allowed_and_mocked(fetcher: ScopedFetcher) -> None:
    """In-scope URL should be fetched."""
    mock_response = AsyncMock(status_code=200, text="<html>ok</html>")
    with patch.object(fetcher.client, "get", return_value=mock_response) as mock_get:
        resp = await fetcher.get("https://app.example.com/page")
        assert resp is not None
        mock_get.assert_called_once_with("https://app.example.com/page")


@pytest.mark.asyncio
async def test_fetch_dry_run(fetcher: ScopedFetcher) -> None:
    """Dry run mode should log and skip fetch."""
    fetcher.config.dry_run = True
    resp = await fetcher.get("https://app.example.com/page")
    assert resp is None
