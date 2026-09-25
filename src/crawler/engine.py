"""Breadth-first crawl engine.

Pulls URLs off the frontier, fetches each one through the scoped fetcher (so
every request passes the scope check and rate limiter), extracts links from
HTML responses, and feeds them back into the frontier at the next depth.

Concurrency is bounded twice over: an overall worker count, and a per-host
semaphore so a single host is never hammered in parallel.  The rate limiter
sets the sustained pace; these semaphores cap what is in flight at any instant.

One crawl per instance: ``crawl()`` appends to the same result list and reuses
the frontier, so a second call continues rather than restarts.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Sequence

from .extractor import extract_absolute_links
from .fetcher import ScopedFetcher
from .frontier import Frontier, FrontierItem
from .robots import RobotsInfo, fetch_robots
from .scope_config import ScopeConfig
from .url_utils import host_of

logger = logging.getLogger(__name__)

HTML_CONTENT_TYPES = ("text/html", "application/xhtml+xml")


@dataclass
class PageResult:
    """What happened at one URL.

    ``status is None`` means the URL was never fetched — out of scope, dry run,
    or a transport error.  The scoped fetcher logs which, with its reason.
    """

    url: str
    depth: int
    status: int | None = None
    final_url: str = ""
    content_type: str = ""
    body_length: int = 0
    is_html: bool = False
    links_found: int = 0
    links_queued: int = 0


@dataclass
class CrawlReport:
    """Everything one crawl run saw."""

    pages: list[PageResult] = field(default_factory=list)
    robots: dict[str, RobotsInfo] = field(default_factory=dict)
    duration: float = 0.0

    @property
    def fetched(self) -> int:
        """Number of URLs that came back with a response."""
        return sum(1 for page in self.pages if page.status is not None)

    @property
    def skipped(self) -> int:
        """Number of URLs that were never fetched."""
        return sum(1 for page in self.pages if page.status is None)

    @property
    def html_pages(self) -> int:
        """Number of responses that were HTML and parsed for links."""
        return sum(1 for page in self.pages if page.is_html)

    @property
    def robots_candidates(self) -> list[tuple[str, str]]:
        """Robots-disallowed paths, as (robots_url, path) pairs.

        Reported for a human to triage — never fetched on this evidence alone,
        and never treated as off-limits either.
        """
        return [
            (info.url, path) for info in self.robots.values() for path in info.disallowed
        ]


class Crawler:
    """Runs a breadth-first crawl over a seeded frontier."""

    def __init__(
        self,
        config: ScopeConfig,
        fetcher: ScopedFetcher | None = None,
        frontier: Frontier | None = None,
        max_concurrency: int = 8,
        per_host_concurrency: int = 4,
        user_agent: str = "*",
    ) -> None:
        self.config = config
        self.fetcher = fetcher if fetcher is not None else ScopedFetcher(config=config)
        self.frontier = (
            frontier
            if frontier is not None
            else Frontier(
                max_depth=config.max_depth,
                max_urls_per_host=config.max_urls_per_host,
            )
        )
        self.max_concurrency = max(1, max_concurrency)
        self.per_host_concurrency = max(1, per_host_concurrency)
        self.user_agent = user_agent

        self.results: list[PageResult] = []
        self._robots: dict[str, RobotsInfo] = {}
        self._robots_locks: dict[str, asyncio.Lock] = {}
        self._host_semaphores: dict[str, asyncio.Semaphore] = {}
        self._capped_hosts: set[str] = set()

        # Worker coordination: a worker that finds the queue empty may only stop
        # once no peer is still fetching, because a peer may yet enqueue links.
        self._in_flight = 0
        self._work_available = asyncio.Event()

    async def crawl(self, seeds: Sequence[str]) -> CrawlReport:
        """Crawl outward from *seeds* and return everything that was seen."""
        for seed in seeds:
            if not self.frontier.add(seed, depth=0):
                logger.warning("SEED-REJECTED %s — not queued (duplicate or over cap)", seed)

        start = time.monotonic()
        if len(self.frontier) == 0:
            logger.warning("Nothing to crawl — no seeds were queued")
            return self._report(start)

        workers = [
            asyncio.create_task(self._worker(), name=f"crawler-worker-{i}")
            for i in range(self.max_concurrency)
        ]
        try:
            await asyncio.gather(*workers)
        except BaseException:
            # Cancelled (Ctrl-C) or a worker raised: never leave peers running.
            for worker in workers:
                worker.cancel()
            await asyncio.gather(*workers, return_exceptions=True)
            raise

        return self._report(start)

    async def _worker(self) -> None:
        """Consume the frontier until the crawl is genuinely finished."""
        while True:
            item = self.frontier.pop()

            if item is None:
                if self._in_flight == 0:
                    # Queue empty and nothing outstanding: everyone can stop.
                    self._work_available.set()  # release peers parked below
                    return
                # A peer is mid-fetch and may still enqueue links.  Clear, then
                # re-check: no await happens in between, so a peer cannot slip
                # an enqueue past the clear unnoticed.
                self._work_available.clear()
                if len(self.frontier) or self._in_flight == 0:
                    continue
                await self._work_available.wait()
                continue

            self._in_flight += 1
            try:
                await self._visit(item)
            finally:
                self._in_flight -= 1

    async def _visit(self, item: FrontierItem) -> None:
        """Fetch one URL, record it, and queue the links it revealed."""
        url = item.url
        host = host_of(url)

        # robots.txt first, once per host, so its findings reach the log before
        # that host's pages are reported.
        await self._robots_for(host, url)

        async with self._semaphore_for(host):
            response = await self.fetcher.get(url)

        if response is None:
            # Blocked, dry run, or transport error — the fetcher logged which.
            logger.debug("NOT-FETCHED %s", url)
            self.results.append(PageResult(url=url, depth=item.depth))
            return

        content_type = response.headers.get("content-type", "")
        is_html = _is_html(content_type)
        body = response.text if is_html else ""
        links = extract_absolute_links(body, str(response.url)) if is_html else []
        queued = self._queue_links(links, item.depth + 1)

        self.results.append(
            PageResult(
                url=url,
                depth=item.depth,
                status=response.status_code,
                final_url=str(response.url),
                content_type=content_type,
                body_length=len(response.content),
                is_html=is_html,
                links_found=len(links),
                links_queued=queued,
            )
        )

    def _queue_links(self, links: Sequence[str], depth: int) -> int:
        """Add discovered links to the frontier, logging the informative skips."""
        queued = 0
        for link in links:
            if self.frontier.add(link, depth):
                queued += 1
            elif depth > self.frontier.max_depth:
                logger.debug(
                    "DEPTH-LIMIT %s — depth %d > %d", link, depth, self.frontier.max_depth
                )
            else:
                self._log_host_cap(link)

        if queued:
            # Wake any peer parked on an empty queue so it can share the work.
            self._work_available.set()
        return queued

    def _log_host_cap(self, url: str) -> None:
        """Say so, once per host, when a host has hit its per-host URL cap."""
        cap = self.frontier.max_urls_per_host
        if not cap:
            return
        host = host_of(url)
        if host in self._capped_hosts or self.frontier.count_for_host(host) < cap:
            return
        self._capped_hosts.add(host)
        logger.info(
            "HOST-CAP %s reached %d URLs — further URLs on this host are skipped", host, cap
        )

    def _semaphore_for(self, host: str) -> asyncio.Semaphore:
        """Per-host in-flight cap.  No await between check and insert."""
        semaphore = self._host_semaphores.get(host)
        if semaphore is None:
            semaphore = asyncio.Semaphore(self.per_host_concurrency)
            self._host_semaphores[host] = semaphore
        return semaphore

    async def _robots_for(self, host: str, url: str) -> RobotsInfo:
        """Fetch robots.txt for *host* at most once, even under concurrency."""
        lock = self._robots_locks.get(host)
        if lock is None:
            lock = asyncio.Lock()
            self._robots_locks[host] = lock
        async with lock:
            info = self._robots.get(host)
            if info is None:
                info = await fetch_robots(self.fetcher, url, user_agent=self.user_agent)
                self._robots[host] = info
            return info

    def _report(self, start: float) -> CrawlReport:
        duration = time.monotonic() - start
        logger.info(
            "CRAWL-DONE %d fetched, %d skipped in %.1fs",
            sum(1 for page in self.results if page.status is not None),
            sum(1 for page in self.results if page.status is None),
            duration,
        )
        return CrawlReport(pages=self.results, robots=dict(self._robots), duration=duration)


def _is_html(content_type: str) -> bool:
    """True when a response body is worth parsing for links.

    A missing Content-Type is treated as HTML: servers omit it often enough that
    refusing to parse would quietly narrow the crawl.
    """
    if not content_type:
        return True
    return any(html_type in content_type.lower() for html_type in HTML_CONTENT_TYPES)
