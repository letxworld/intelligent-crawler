"""Tests for DOM link extraction from headless-rendered pages."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from crawler.dom_extractor import (
    DOM_LINK_ATTRIBUTES,
    _resolve_links,
    extract_dom_links,
    extract_dom_links_with_text,
)


class _FakeElement:
    """A mock Playwright element handle."""

    def __init__(self, tag: str, attr_value: str | None, text: str = "") -> None:
        self._tag = tag
        self._attr_value = attr_value
        self._text = text

    async def get_attribute(self, name: str) -> str | None:
        if name == "href" or name == "action" or name == "src":
            return self._attr_value
        return None

    async def evaluate(self, expr: str) -> str:
        if "tagName" in expr:
            return self._tag.lower()
        if "innerText" in expr or "textContent" in expr:
            return self._text
        return ""


def test_resolve_links_relative() -> None:
    links = _resolve_links(["/about", "docs/intro.html", "#top", "mailto:hi@example.com", ""], "https://app.example.com/dir/page.html")
    assert "https://app.example.com/about" in links
    assert "https://app.example.com/dir/docs/intro.html" in links
    assert not any(link.startswith("mailto:") for link in links)
    assert "https://app.example.com/dir/page.html" not in links  # fragment dropped


def test_resolve_links_absolute_passthrough() -> None:
    links = _resolve_links(["https://other.example.com/widget", ""], "https://app.example.com/")
    assert "https://other.example.com/widget" in links


def test_resolve_links_duplicates_preserved() -> None:
    links = _resolve_links(["/a", "/a"], "https://app.example.com/")
    assert links.count("https://app.example.com/a") == 2


def test_dom_link_attributes_coverage() -> None:
    assert DOM_LINK_ATTRIBUTES == {
        "a": "href",
        "area": "href",
        "form": "action",
        "link": "href",
        "iframe": "src",
        "frame": "src",
    }


@pytest.mark.asyncio
async def test_extract_dom_links_basic() -> None:
    page = _make_fake_page([
        _FakeElement("a", "/about"),
        _FakeElement("a", "https://other.example.com/widget"),
        _FakeElement("a", "#top"),
        _FakeElement("a", "mailto:hi@example.com"),
        _FakeElement("form", "/search"),
        _FakeElement("iframe", "https://embed.example.com/widget"),
    ])

    links = await extract_dom_links(page, "https://app.example.com/dir/page.html")
    assert "https://app.example.com/about" in links
    assert "https://other.example.com/widget" in links
    assert not any(link.startswith("mailto:") for link in links)
    assert "https://app.example.com/search" in links
    assert "https://embed.example.com/widget" in links


@pytest.mark.asyncio
async def test_extract_dom_links_empty_page() -> None:
    page = _make_fake_page([])
    links = await extract_dom_links(page, "https://app.example.com/")
    assert links == []


@pytest.mark.asyncio
async def test_extract_dom_links_error_handling() -> None:
    page = MagicMock()
    page.query_selector_all = AsyncMock(side_effect=Exception("playwright crashed"))
    links = await extract_dom_links(page, "https://app.example.com/")
    assert links == []


@pytest.mark.asyncio
async def test_extract_dom_links_with_text() -> None:
    page = _make_fake_page([
        _FakeElement("a", "/login", "Log in"),
        _FakeElement("a", "/dashboard", "My Dashboard"),
        _FakeElement("a", "#top", "Back to top"),
        _FakeElement("a", "", ""),  # no href
    ])

    pairs = await extract_dom_links_with_text(page, "https://app.example.com/")
    assert ("https://app.example.com/login", "Log in") in pairs
    assert ("https://app.example.com/dashboard", "My Dashboard") in pairs
    assert len(pairs) == 2


@pytest.mark.asyncio
async def test_extract_dom_links_with_text_error_handling() -> None:
    page = MagicMock()
    page.query_selector_all = AsyncMock(side_effect=Exception("fail"))
    pairs = await extract_dom_links_with_text(page, "https://app.example.com/")
    assert pairs == []


def _make_fake_page(elements: list[_FakeElement]) -> MagicMock:
    """Build a fake Playwright Page whose query_selector_all returns *elements*."""
    page = MagicMock()
    page.query_selector_all = AsyncMock(return_value=elements)
    return page
