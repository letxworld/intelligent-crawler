"""Unit tests for URL normalization."""

from __future__ import annotations

import pytest

from crawler.url_utils import host_of, normalize_url, resolve_url


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Scheme + host lower-cased.
        ("HTTPS://APP.Example.COM/Page", "https://app.example.com/Page"),
        # Default port dropped, non-default port kept.
        ("https://app.example.com:443/x", "https://app.example.com/x"),
        ("http://app.example.com:80/x", "http://app.example.com/x"),
        ("https://app.example.com:8443/x", "https://app.example.com:8443/x"),
        # Fragment stripped, query parameters sorted.
        ("https://app.example.com/x?b=2&a=1#frag", "https://app.example.com/x?a=1&b=2"),
        # Dot-segments resolved, duplicate slashes collapsed.
        ("https://app.example.com/a/b/../c", "https://app.example.com/a/c"),
        ("https://app.example.com//a///b", "https://app.example.com/a/b"),
        # Empty path becomes "/", trailing slash preserved.
        ("https://app.example.com", "https://app.example.com/"),
        ("https://app.example.com/a/", "https://app.example.com/a/"),
        # Surrounding whitespace tolerated.
        ("  https://app.example.com/x  ", "https://app.example.com/x"),
    ],
)
def test_normalize_url_canonicalizes(raw: str, expected: str) -> None:
    assert normalize_url(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "mailto:someone@example.com",
        "javascript:void(0)",
        "data:text/html,<h1>hi</h1>",
        "ftp://app.example.com/file",
        "https:///no-host",
        "",
        "not a url",
        "https://app.example.com:notaport/x",
    ],
)
def test_normalize_url_rejects_uncrawlable(raw: str) -> None:
    assert normalize_url(raw) == ""


def test_normalize_is_idempotent() -> None:
    once = normalize_url("HTTPS://App.Example.com:443/a/../b/?z=1&a=2#x")
    assert normalize_url(once) == once


def test_resolve_url_relative() -> None:
    base = "https://app.example.com/dir/page.html"
    assert resolve_url(base, "sub/x.html") == "https://app.example.com/dir/sub/x.html"
    assert resolve_url(base, "/root.html") == "https://app.example.com/root.html"
    assert resolve_url(base, "../up.html") == "https://app.example.com/up.html"
    assert resolve_url(base, "#section") == "https://app.example.com/dir/page.html"


def test_resolve_url_drops_non_http() -> None:
    base = "https://app.example.com/"
    assert resolve_url(base, "javascript:alert(1)") == ""
    assert resolve_url(base, "mailto:a@b.com") == ""
    assert resolve_url(base, "") == ""


def test_host_of() -> None:
    assert host_of("https://APP.Example.com:8443/x") == "app.example.com"
    assert host_of("not a url") == ""
