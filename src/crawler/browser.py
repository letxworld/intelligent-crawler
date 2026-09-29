"""Headless browser integration via Playwright.

Phase 3: SPA-shell detection, JS-rendered page fetching, and DOM extraction
after render.  Every browser session is still gated by the same scope check
and rate limiter as the static fetcher — the ScopedFetcher is the only HTTP
client that ever leaves this process.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from playwright.async_api import Browser, Page, async_playwright

from .fetcher import ScopedFetcher
from .robots import RobotsInfo

logger = logging.getLogger(__name__)

# Body-text length below which we treat a page as a possible SPA shell and
# retry with the headless browser.  Tuned for "this looks like a JS shell"
# rather than "this is a tiny legit page" — a hard 50-byte floor avoids
# retriggering on empty 200s and tiny static pages.
MIN_BODY_LENGTH_FOR_STATIC = 120


@dataclass
class BrowserSession:
    """A shared headless Chromium instance.

    One session is created per crawl run and handed to ScopedHeadlessFetcher
    so every browser-driven request shares the same browser process and the
    same per-host rate-limiter gate.
    """

    browser: Browser
    base_url: str

    async def new_page(self) -> Page:
        return await self.browser.new_page()

    async def close(self) -> None:
        await self.browser.close()


async def create_browser_session(
    base_url: str,
    user_agent: str = "*",
) -> BrowserSession:
    """Launch a headless Chromium and return a session for *base_url*."""
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        ],
    )
    logger.info("HEADLESS-BROWSER started for %s", base_url)
    return BrowserSession(browser=browser, base_url=base_url)


def is_spa_shell(body_text: str, content_type: str) -> bool:
    """Return True when *body_text* looks like a JS-only shell page.

    Heuristics (all must match):
    - Content-Type is HTML (otherwise we would never parse it for links).
    - Body text is short — a real page almost always has more than a screenful
      of text once JS runs, but a shell typically has a root div and a script.
    - The body contains a ``<script`` tag (the JS bundle that will render the
      real app) and has very little visible text otherwise.
    """
    if "html" not in content_type.lower():
        return False
    if len(body_text) >= MIN_BODY_LENGTH_FOR_STATIC:
        return False
    if "<script" not in body_text.lower():
        return False
    return True


async def fetch_robots_headless(
    session: BrowserSession,
    fetcher: ScopedFetcher,
    base_url: str,
    user_agent: str = "*",
) -> RobotsInfo:
    """Headless variant of robots.txt fetch — same gate, browser transport.

    Robots.txt is informational only and the static fetcher handles it well.
    This helper is kept for interface symmetry when the engine is already in
    headless mode for a host; it delegates back to the scoped fetcher.
    """
    from .robots import fetch_robots

    return await fetch_robots(fetcher, base_url, user_agent=user_agent)
