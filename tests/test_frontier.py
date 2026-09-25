"""Unit tests for the crawl frontier."""

from __future__ import annotations

from crawler.frontier import Frontier
from crawler.seen_set import SeenSet


def test_fifo_order() -> None:
    frontier = Frontier()
    frontier.add("https://app.example.com/a")
    frontier.add("https://app.example.com/b")
    assert len(frontier) == 2
    assert frontier.pop().url == "https://app.example.com/a"
    assert frontier.pop().url == "https://app.example.com/b"
    assert frontier.pop() is None


def test_depth_is_tracked_and_capped() -> None:
    frontier = Frontier(max_depth=2)
    assert frontier.add("https://app.example.com/d0", depth=0)
    assert frontier.add("https://app.example.com/d2", depth=2)
    assert not frontier.add("https://app.example.com/d3", depth=3)
    assert len(frontier) == 2


def test_duplicate_urls_are_dropped_after_normalization() -> None:
    frontier = Frontier()
    assert frontier.add("HTTPS://App.Example.com/x?a=1&b=2#frag")
    # Same page, different spelling — must not be queued twice.
    assert not frontier.add("https://app.example.com/x?b=2&a=1")
    assert len(frontier) == 1


def test_per_host_cap() -> None:
    frontier = Frontier(max_urls_per_host=2)
    assert frontier.add("https://app.example.com/1")
    assert frontier.add("https://app.example.com/2")
    assert not frontier.add("https://app.example.com/3")
    # A different host is unaffected and still gets its own budget.
    assert frontier.add("https://api.example.com/1")
    assert frontier.count_for_host("app.example.com") == 2
    assert frontier.count_for_host("api.example.com") == 1
    assert frontier.host_count == 2


def test_unlimited_per_host_by_default() -> None:
    frontier = Frontier()
    for index in range(50):
        assert frontier.add(f"https://app.example.com/{index}")
    assert frontier.count_for_host("app.example.com") == 50


def test_uncrawlable_urls_rejected() -> None:
    frontier = Frontier()
    assert not frontier.add("mailto:someone@example.com")
    assert not frontier.add("javascript:void(0)")
    assert len(frontier) == 0


def test_seen_set_is_injectable() -> None:
    """The frontier accepts any SeenSet backend."""

    class _Refusing(SeenSet):
        def add(self, url: str) -> bool:
            return False

        def __contains__(self, url: str) -> bool:
            return True

        def __len__(self) -> int:
            return 0

    frontier = Frontier(seen=_Refusing())
    assert not frontier.add("https://app.example.com/a")
    assert len(frontier) == 0
