"""Seen-set interface for crawl deduplication.

Phase 2 uses an exact hash set: at this scale it is cheap and has no false
positives.  The interface exists so a Bloom filter (probabilistic, memory-bounded)
or a Redis-backed set can replace it later without the crawl engine noticing.

Implementations deal in already-normalized URLs — callers normalize first.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable


class SeenSet(ABC):
    """Tracks which URLs have already been queued for crawling."""

    @abstractmethod
    def add(self, url: str) -> bool:
        """Record *url* and return True if it had not been seen before."""

    @abstractmethod
    def __contains__(self, url: str) -> bool:
        """Return True if *url* has already been seen."""

    @abstractmethod
    def __len__(self) -> int:
        """Return the number of distinct URLs seen so far."""


class HashSetSeenSet(SeenSet):
    """Exact dedup backed by a Python set."""

    def __init__(self, initial: Iterable[str] | None = None) -> None:
        self._seen: set[str] = set(initial or ())

    def add(self, url: str) -> bool:
        if url in self._seen:
            return False
        self._seen.add(url)
        return True

    def __contains__(self, url: str) -> bool:
        return url in self._seen

    def __len__(self) -> int:
        return len(self._seen)
