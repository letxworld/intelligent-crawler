"""Scoped fetch wrapper — every HTTP request goes through scope-check + rate limiter."""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from .rate_limiter import RateLimiter
from .scope_check import check_scope
from .scope_config import ScopeConfig

logger = logging.getLogger(__name__)


class ScopedFetcher:
    """HTTP client that gates every request through the scope checker."""

    def __init__(
        self,
        config: ScopeConfig,
        rate_limiter: Optional[RateLimiter] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.config = config
        self.rate_limiter = rate_limiter
        self.client = client or httpx.AsyncClient(follow_redirects=True, timeout=10.0)

    async def get(self, url: str) -> Optional[httpx.Response]:
        """Fetch a URL if it passes scope and rate limits. Returns None if blocked."""
        allowed, reason = check_scope(url, self.config)
        if not allowed:
            logger.warning("BLOCKED %s — %s", url, reason)
            return None

        if self.rate_limiter:
            await self.rate_limiter.acquire(url)

        if self.config.dry_run:
            logger.info("DRY-RUN skip fetch: %s", url)
            return None

        try:
            response = await self.client.get(url)
            logger.info("FETCH %s -> %d", url, response.status_code)
            return response
        except httpx.HTTPError as exc:
            logger.error("FETCH-ERROR %s — %s", url, exc)
            return None

    async def close(self) -> None:
        await self.client.aclose()
