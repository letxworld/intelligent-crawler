"""Unit tests for robots.txt parsing and informational fetching."""

from __future__ import annotations

import httpx
import pytest

from crawler.fetcher import ScopedFetcher
from crawler.robots import RobotsInfo, fetch_robots, parse_robots
from crawler.scope_config import ScopeConfig

ROBOTS = """
# a leading comment
User-agent: *
Disallow: /admin/
Disallow: /backup
Allow: /admin/public
Disallow:
Sitemap: https://app.example.com/sitemap.xml

User-agent: Googlebot
Disallow: /nothing
"""


class _StubFetcher:
    """Stands in for ScopedFetcher, recording the URLs it was asked for."""

    def __init__(self, response: httpx.Response | None) -> None:
        self.response = response
        self.requested: list[str] = []

    async def get(self, url: str) -> httpx.Response | None:
        self.requested.append(url)
        return self.response


def _response(status: int, text: str = "") -> httpx.Response:
    url = "https://app.example.com/robots.txt"
    return httpx.Response(status, text=text, request=httpx.Request("GET", url))


def test_parse_wildcard_group() -> None:
    info = parse_robots(ROBOTS)
    assert info.disallowed == ("/admin/", "/backup")
    assert info.allowed == ("/admin/public",)
    assert info.sitemaps == ("https://app.example.com/sitemap.xml",)


def test_empty_disallow_value_is_not_a_rule() -> None:
    """`Disallow:` with no value means "no restriction", not "disallow all"."""
    assert parse_robots(ROBOTS).disallowed.count("") == 0


def test_specific_user_agent_group_wins_over_wildcard() -> None:
    info = parse_robots(ROBOTS, "Googlebot")
    assert info.disallowed == ("/nothing",)


def test_unknown_user_agent_falls_back_to_wildcard() -> None:
    info = parse_robots(ROBOTS, "some-other-bot")
    assert info.disallowed == ("/admin/", "/backup")


def test_no_matching_group_yields_no_rules() -> None:
    info = parse_robots("User-agent: Googlebot\nDisallow: /x", "*")
    assert info.disallowed == ()


def test_consecutive_user_agent_lines_share_one_group() -> None:
    text = "User-agent: alpha\nUser-agent: beta\nDisallow: /x"
    assert parse_robots(text, "beta").disallowed == ("/x",)
    assert parse_robots(text, "alpha").disallowed == ("/x",)


def test_rules_before_any_user_agent_are_ignored() -> None:
    text = "Disallow: /orphan\nUser-agent: *\nDisallow: /kept"
    assert parse_robots(text).disallowed == ("/kept",)


def test_wildcard_path_patterns_are_preserved_verbatim() -> None:
    """Nothing here gates a fetch, so patterns are reported as written."""
    info = parse_robots("User-agent: *\nDisallow: /*.pdf$\nDisallow: /tmp/*/secret")
    assert info.disallowed == ("/*.pdf$", "/tmp/*/secret")


@pytest.mark.asyncio
async def test_fetch_robots_parses_body() -> None:
    fetcher = _StubFetcher(_response(200, ROBOTS))
    info = await fetch_robots(fetcher, "https://app.example.com/dir/page.html")

    assert info.fetched
    assert info.status == 200
    assert info.disallowed == ("/admin/", "/backup")
    # robots.txt always lives at the host root, never beside the page.
    assert fetcher.requested == ["https://app.example.com/robots.txt"]


@pytest.mark.asyncio
async def test_fetch_robots_missing_file_is_not_an_error() -> None:
    fetcher = _StubFetcher(_response(404))
    info = await fetch_robots(fetcher, "https://app.example.com/")

    assert info.status == 404
    assert not info.fetched
    assert info.disallowed == ()
    assert info.error is None


@pytest.mark.asyncio
async def test_fetch_robots_reports_dropped_fetch() -> None:
    """A fetcher that returns None (blocked, dry-run, error) yields no rules."""
    fetcher = _StubFetcher(None)
    info = await fetch_robots(fetcher, "https://app.example.com/")

    assert info.status is None
    assert not info.fetched
    assert info.error is not None


@pytest.mark.asyncio
async def test_robots_fetch_is_blocked_for_out_of_scope_host() -> None:
    """robots.txt is subject to the scope gate like any other URL."""
    config = ScopeConfig(allowed_domains=["*.example.com"])
    fetcher = ScopedFetcher(config=config)
    try:
        info = await fetch_robots(fetcher, "https://evil.org/")
    finally:
        await fetcher.close()

    assert info.status is None
    assert info.disallowed == ()


@pytest.mark.asyncio
async def test_robots_fetch_respects_dry_run() -> None:
    """dry_run short-circuits before any request leaves the process."""
    config = ScopeConfig(allowed_domains=["*.example.com"], dry_run=True)
    fetcher = ScopedFetcher(config=config)
    try:
        info = await fetch_robots(fetcher, "https://app.example.com/")
    finally:
        await fetcher.close()

    assert isinstance(info, RobotsInfo)
    assert info.status is None
    assert info.error is not None
