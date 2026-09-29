"""Scoped fetch wrapper — every HTTP request goes through scope-check + rate limiter."""

from __future__ import annotations

import logging
from typing import Optional, TYPE_CHECKING

import httpx

from .rate_limiter import RateLimiter
from .scope_check import check_scope
from .scope_config import ScopeConfig

if TYPE_CHECKING:
    from playwright.async_api import Page, Response as PlaywrightResponse

logger = logging.getLogger(__name__)


class ScopedFetcher:
    """HTTP client that gates every request through the scope checker.

    Two fetch methods share the same gate:
    - ``get()`` — static HTTP via httpx.
    - ``get_headless()`` — headless browser via Playwright.

    Every request, regardless of transport, passes through ``check_scope()``
    and the rate limiter.  There is no second HTTP client.
    """

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

    async def get_headless(
        self, url: str, page: "Page"
    ) -> Optional["PlaywrightResponse"]:
        """Fetch *url* through the headless browser, gated by scope + rate limiter.

        The page navigates to *url* and the Playwright response is returned.
        Every request still passes through ``check_scope()`` and the rate
        limiter — there is no second HTTP client, browser or not.
        """
        allowed, reason = check_scope(url, self.config)
        if not allowed:
            logger.warning("BLOCKED %s — %s", url, reason)
            return None

        if self.rate_limiter:
            await self.rate_limiter.acquire(url)

        if self.config.dry_run:
            logger.info("DRY-RUN skip headless fetch: %s", url)
            return None

        try:
            playwright_resp: "PlaywrightResponse" = await page.goto(
                url, wait_until="domcontentloaded", timeout=15000
            )
            logger.info("FETCH-HEADLESS %s -> %d", url, playwright_resp.status)
            return playwright_resp  # type: ignore[return-value]
        except Exception as exc:
            logger.error("FETCH-HEADLESS-ERROR %s — %s", url, exc)
            return None

    async def close(self) -> None:
        await self.client.aclose()
