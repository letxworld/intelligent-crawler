"""Unit tests for the seen-set interface."""

from __future__ import annotations

import pytest

from crawler.seen_set import HashSetSeenSet, SeenSet


def test_add_returns_true_only_first_time() -> None:
    seen = HashSetSeenSet()
    assert seen.add("https://app.example.com/a") is True
    assert seen.add("https://app.example.com/a") is False


def test_contains_and_len() -> None:
    seen = HashSetSeenSet()
    seen.add("https://app.example.com/a")
    seen.add("https://app.example.com/b")
    seen.add("https://app.example.com/a")
    assert "https://app.example.com/a" in seen
    assert "https://app.example.com/zzz" not in seen
    assert len(seen) == 2


def test_initial_members() -> None:
    seen = HashSetSeenSet(["https://app.example.com/a"])
    assert "https://app.example.com/a" in seen
    assert seen.add("https://app.example.com/a") is False


def test_seen_set_is_abstract() -> None:
    """The interface cannot be instantiated directly — it is a contract."""
    with pytest.raises(TypeError):
        SeenSet()  # type: ignore[abstract]


def test_implementation_is_swappable() -> None:
    """A different backend satisfies the same contract (Bloom filter later)."""

    class _OneShot(SeenSet):
        def __init__(self) -> None:
            self.seen: list[str] = []

        def add(self, url: str) -> bool:
            if url in self.seen:
                return False
            self.seen.append(url)
            return True

        def __contains__(self, url: str) -> bool:
            return url in self.seen

        def __len__(self) -> int:
            return len(self.seen)

    backend: SeenSet = _OneShot()
    assert backend.add("https://app.example.com/a") is True
    assert backend.add("https://app.example.com/a") is False
    assert len(backend) == 1
