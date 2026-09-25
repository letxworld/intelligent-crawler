"""Breadth-first crawl frontier.

Holds the URLs still to visit, enforces the depth limit, and applies a per-host
cap so crawl traps (pagination loops, calendar "next" links, faceted-search
combinatorics) cannot consume the whole budget.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from .seen_set import HashSetSeenSet, SeenSet
from .url_utils import host_of, normalize_url


@dataclass(frozen=True)
class FrontierItem:
    """A queued URL together with the depth at which it was discovered."""

    url: str
    depth: int


class Frontier:
    """FIFO queue of normalized, de-duplicated, depth-bounded URLs."""

    def __init__(
        self,
        max_depth: int = 5,
        max_urls_per_host: int = 0,
        seen: SeenSet | None = None,
    ) -> None:
        self.max_depth = max_depth
        self.max_urls_per_host = max_urls_per_host  # 0 means unlimited
        # `is None` rather than truthiness: an empty backend is falsy.
        self.seen = HashSetSeenSet() if seen is None else seen
        self._queue: deque[FrontierItem] = deque()
        self._host_counts: dict[str, int] = {}

    def add(self, url: str, depth: int = 0) -> bool:
        """Queue *url* if it is new, within depth, and under its host cap.

        Returns True when the URL was queued.  Rejections are silent: the
        caller decides what is worth logging (duplicates are constant noise,
        depth and host-cap skips are interesting).
        """
        if depth > self.max_depth:
            return False

        normalized = normalize_url(url)
        if not normalized:
            return False

        host = host_of(normalized)
        if self.max_urls_per_host and self._host_counts.get(host, 0) >= self.max_urls_per_host:
            return False

        if not self.seen.add(normalized):
            return False

        self._host_counts[host] = self._host_counts.get(host, 0) + 1
        self._queue.append(FrontierItem(url=normalized, depth=depth))
        return True

    def pop(self) -> FrontierItem | None:
        """Return the next item to visit, or None when the queue is drained."""
        return self._queue.popleft() if self._queue else None

    def count_for_host(self, host: str) -> int:
        """Return how many URLs of *host* have been queued so far."""
        return self._host_counts.get(host.lower(), 0)

    @property
    def host_count(self) -> int:
        """Return the number of distinct hosts queued so far."""
        return len(self._host_counts)

    def __len__(self) -> int:
        return len(self._queue)
