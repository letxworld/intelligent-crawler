"""Unit tests for static link extraction."""

from __future__ import annotations

from crawler.extractor import extract_absolute_links, extract_links

PAGE = """
<html>
  <head>
    <link rel="stylesheet" href="/static/app.css" />
    <link rel="icon" href="favicon.ico" />
  </head>
  <body>
    <a href="/about">About</a>
    <a href="docs/intro.html">Docs</a>
    <a href="#top">Back to top</a>
    <a href="mailto:hi@example.com">Mail</a>
    <a href="javascript:void(0)">JS</a>
    <a>No href here</a>
    <form action="/search" method="get"><input name="q" /></form>
    <iframe src="https://embed.example.com/widget"></iframe>
    <area href="/map" />
  </body>
</html>
"""


def test_extract_raw_links() -> None:
    links = extract_links(PAGE)
    assert "/static/app.css" in links
    assert "favicon.ico" in links
    assert "/about" in links
    assert "/search" in links
    assert "https://embed.example.com/widget" in links
    assert "/map" in links


def test_self_closing_tag_collected_once() -> None:
    """<link ... /> must not be collected by both start handlers."""
    links = extract_links('<link rel="stylesheet" href="/a.css" />')
    assert links == ["/a.css"]


def test_extract_absolute_links_resolves_and_filters() -> None:
    links = extract_absolute_links(PAGE, "https://app.example.com/dir/page.html")
    assert "https://app.example.com/static/app.css" in links
    assert "https://app.example.com/dir/favicon.ico" in links
    assert "https://app.example.com/about" in links
    assert "https://app.example.com/dir/docs/intro.html" in links
    assert "https://app.example.com/search" in links
    assert "https://embed.example.com/widget" in links


def test_non_crawlable_links_dropped() -> None:
    links = extract_absolute_links(PAGE, "https://app.example.com/dir/page.html")
    assert not any(link.startswith("mailto:") for link in links)
    assert not any(link.startswith("javascript:") for link in links)
    # "#top" resolves back to the page itself and is dropped as non-crawlable.
    assert links.count("https://app.example.com/dir/page.html") == 0


def test_tag_without_target_attribute_is_skipped() -> None:
    assert extract_links("<a>bare</a><a href="">empty</a>") == []


def test_base_href_overrides_resolution_base() -> None:
    html = """
    <html><head><base href="/app/" /></head>
    <body><a href="dashboard">Dash</a><a href="https://other.example.com/x">Abs</a></body></html>
    """
    links = extract_absolute_links(html, "https://app.example.com/dir/page.html")
    assert "https://app.example.com/app/dashboard" in links
    assert "https://other.example.com/x" in links


def test_relative_base_href_resolves_against_page_url() -> None:
    html = '<base href="v2/"><a href="users">Users</a>'
    links = extract_absolute_links(html, "https://app.example.com/api/")
    assert links == ["https://app.example.com/api/v2/users"]


def test_uncrawlable_base_href_is_ignored() -> None:
    """A junk <base> must not poison every relative link on the page."""
    html = '<base href="mailto:hi@example.com"><a href="/about">About</a>'
    links = extract_absolute_links(html, "https://app.example.com/dir/page.html")
    assert links == ["https://app.example.com/about"]


def test_first_base_href_wins() -> None:
    html = '<base href="/one/"><base href="/two/"><a href="x">X</a>'
    links = extract_absolute_links(html, "https://app.example.com/")
    assert links == ["https://app.example.com/one/x"]


def test_empty_and_malformed_html() -> None:
    assert extract_links("") == []
    assert extract_links("<a href='/x' <b>unclosed") == ["/x"]
