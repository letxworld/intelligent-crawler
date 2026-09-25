"""Tests for the crawl engine.

These run a real ScopedFetcher over an httpx MockTransport, so the scope gate,
the robots fetch and the crawl loop are all exercised end to end — only the
socket is fake.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from crawler.engine import Crawler, CrawlReport, PageResult
from crawler.fetcher import ScopedFetcher
from crawler.rate_limiter import RateLimiter
from crawler.scope_config import ScopeConfig

SCOPE_HOST = "app.example.com"


def _html(*links: str) -> str:
    return "".join(f'<a href="{link}">link</a>' for link in links)


class _Site:
    """A fake site: path -> (status, content-type, body), plus optional robots."""

    def __init__(
        self,
        pages: dict[str, tuple[int, str, str]],
        robots: str | None = None,
        delay: float = 0.0,
    ) -> None:
        self.pages = pages
        self.robots = robots
        self.delay = delay
        self.requested: list[str] = []

    async def handler(self, request: httpx.Request) -> httpx.Response:
        self.requested.append(str(request.url))
        if self.delay:
            await asyncio.sleep(self.delay)

        if request.url.path == "/robots.txt":
            if self.robots is None:
                return httpx.Response(404, request=request)
            return httpx.Response(
                200, headers={"content-type": "text/plain"}, text=self.robots, request=request
            )

        status, content_type, body = self.pages.get(request.url.path, (404, "text/html", ""))
        if not content_type:
            # Build from bytes: httpx would otherwise add a default text/plain
            # header, and the point here is to have no Content-Type at all.
            return httpx.Response(status, content=body.encode(), request=request)
        return httpx.Response(
            status, headers={"content-type": content_type}, text=body, request=request
        )

    def paths_requested(self) -> list[str]:
        return [httpx.URL(url).path for url in self.requested]


async def _run(
    site: _Site,
    seeds: list[str],
    *,
    allowed: tuple[str, ...] = (SCOPE_HOST,),
    max_depth: int = 5,
    max_urls_per_host: int = 0,
    dry_run: bool = False,
    rate_limiter: RateLimiter | None = None,
    max_concurrency: int = 8,
    per_host_concurrency: int = 4,
) -> CrawlReport:
    """Run one crawl against *site* through the real scope gate."""
    config = ScopeConfig(
        allowed_domains=list(allowed),
        max_depth=max_depth,
        max_urls_per_host=max_urls_per_host,
        dry_run=dry_run,
    )
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(site.handler), follow_redirects=True
    )
    fetcher = ScopedFetcher(config=config, rate_limiter=rate_limiter, client=client)
    crawler = Crawler(
        config,
        fetcher=fetcher,
        max_concurrency=max_concurrency,
        per_host_concurrency=per_host_concurrency,
    )
    try:
        return await crawler.crawl(seeds)
    finally:
        await fetcher.close()


def _url(path: str) -> str:
    return f"https://{SCOPE_HOST}{path}"


def _by_url(report: CrawlReport) -> dict[str, PageResult]:
    return {page.url: page for page in report.pages}


@pytest.mark.asyncio
async def test_crawls_outward_from_seed() -> None:
    site = _Site(
        {
            "/": (200, "text/html", _html("/a", "/b")),
            "/a": (200, "text/html", _html("/c")),
            "/b": (200, "text/html", "no links"),
            "/c": (200, "text/html", "leaf"),
        }
    )
    report = await _run(site, [_url("/")])

    pages = _by_url(report)
    assert set(pages) >= {_url(p) for p in ("/", "/a", "/b", "/c")}
    assert pages[_url("/")].depth == 0
    assert pages[_url("/a")].depth == 1
    assert pages[_url("/c")].depth == 2
    assert pages[_url("/")].links_queued == 2
    assert report.fetched == 4
    assert report.skipped == 0


@pytest.mark.asyncio
async def test_max_depth_stops_descent() -> None:
    site = _Site(
        {
            "/": (200, "text/html", _html("/level1")),
            "/level1": (200, "text/html", _html("/level2")),
            "/level2": (200, "text/html", _html("/level3")),
        }
    )
    report = await _run(site, [_url("/")], max_depth=1)

    assert _url("/level1") in _by_url(report)
    assert _url("/level2") not in _by_url(report)
    assert "/level2" not in site.paths_requested()


@pytest.mark.asyncio
async def test_out_of_scope_link_is_never_requested() -> None:
    site = _Site({"/": (200, "text/html", _html("https://evil.org/loot", "/in-scope"))})
    report = await _run(site, [_url("/")])

    assert not any("evil.org" in url for url in site.requested)
    # The blocked URL is recorded, not silently dropped.
    blocked = _by_url(report)["https://evil.org/loot"]
    assert blocked.status is None
    assert report.skipped == 1


@pytest.mark.asyncio
async def test_dry_run_fetches_nothing_at_all() -> None:
    site = _Site({"/": (200, "text/html", _html("/a"))})
    report = await _run(site, [_url("/")], dry_run=True)

    assert site.requested == []
    assert report.fetched == 0
    assert report.skipped == 1


@pytest.mark.asyncio
async def test_rate_limiter_is_in_the_fetch_path() -> None:
    site = _Site({"/": (200, "text/html", _html("/a")), "/a": (200, "text/html", "")})
    limiter = RateLimiter(global_rate=1000.0, per_host_rate=1000.0)
    report = await _run(site, [_url("/")], rate_limiter=limiter)

    assert report.fetched == 2


@pytest.mark.asyncio
async def test_robots_fetched_once_per_host() -> None:
    site = _Site(
        {
            "/": (200, "text/html", _html("/a", "/b")),
            "/a": (200, "text/html", _html("/c")),
            "/b": (200, "text/html", ""),
            "/c": (200, "text/html", ""),
        },
        robots="User-agent: *\nDisallow: /secret/\n",
    )
    report = await _run(site, [_url("/")])

    assert site.paths_requested().count("/robots.txt") == 1
    assert report.robots_candidates == [(_url("/robots.txt"), "/secret/")]


@pytest.mark.asyncio
async def test_robots_disallow_is_not_a_boundary() -> None:
    """A disallowed path is reported as a candidate, and still crawled."""
    site = _Site(
        {"/": (200, "text/html", _html("/secret/page")), "/secret/page": (200, "text/html", "")},
        robots="User-agent: *\nDisallow: /secret/\n",
    )
    report = await _run(site, [_url("/")])

    assert "/secret/page" in site.paths_requested()
    assert _by_url(report)[_url("/secret/page")].status == 200
    assert (_url("/robots.txt"), "/secret/") in report.robots_candidates


@pytest.mark.asyncio
async def test_non_html_body_is_not_parsed_for_links() -> None:
    site = _Site(
        {
            "/": (200, "text/html", _html("/doc.pdf")),
            "/doc.pdf": (200, "application/pdf", _html("/should-not-be-found")),
        }
    )
    report = await _run(site, [_url("/")])

    pages = _by_url(report)
    assert pages[_url("/doc.pdf")].is_html is False
    assert "/should-not-be-found" not in site.paths_requested()
    assert report.html_pages == 1


@pytest.mark.asyncio
async def test_missing_content_type_is_parsed_as_html() -> None:
    site = _Site({"/": (200, "", _html("/a")), "/a": (200, "text/html", "")})
    report = await _run(site, [_url("/")])

    assert _url("/a") in _by_url(report)


@pytest.mark.asyncio
async def test_per_host_url_cap_truncates_the_crawl() -> None:
    site = _Site({"/": (200, "text/html", _html("/a", "/b", "/c"))})
    report = await _run(site, [_url("/")], max_urls_per_host=2)

    # The seed used one slot, /a the other; /b and /c are over the cap.
    assert report.fetched == 2
    assert "/b" not in site.paths_requested()


@pytest.mark.asyncio
async def test_workers_do_not_exit_while_a_peer_may_still_enqueue() -> None:
    """Regression: a deep chain must not be cut short by idle workers quitting."""
    pages = {"/": (200, "text/html", _html("/p1"))}
    for i in range(1, 12):
        pages[f"/p{i}"] = (200, "text/html", _html(f"/p{i + 1}"))
    pages["/p12"] = (200, "text/html", "leaf")

    site = _Site(pages, delay=0.01)
    report = await _run(site, [_url("/")], max_concurrency=4, max_depth=20)

    assert report.fetched == 13
    assert _by_url(report)[_url("/p12")].depth == 12


@pytest.mark.asyncio
async def test_seed_that_is_not_an_absolute_url_is_rejected() -> None:
    site = _Site({"/": (200, "text/html", _html("/a"))})
    report = await _run(site, ["example.com"])

    assert report.pages == []
    assert site.requested == []


@pytest.mark.asyncio
async def test_duplicate_seeds_are_crawled_once() -> None:
    site = _Site({"/": (200, "text/html", "")})
    report = await _run(site, [_url("/"), _url("/"), _url("/#fragment")])

    assert report.fetched == 1
    assert site.paths_requested().count("/") == 1
