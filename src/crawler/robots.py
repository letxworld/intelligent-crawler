"""robots.txt handling — informational, never authorization.

robots.txt is fetched so its contents end up in the crawl record: a path an
owner bothered to hide is a good recon lead, and the sitemap lines hand us URLs
for free.  It is deliberately *not* treated as a boundary — a ``Disallow`` is
not a reason to look away, and it is not permission to proceed either.  The
scope config remains the only authorization source, and rules listed here never
block a request or authorize one.

Every request this module makes goes through the scoped fetcher, so robots.txt
is subject to the same scope check and rate limiter as any other URL.  The
``Crawl-delay`` directive is ignored on purpose: our configured limiter governs
pace, not robots.txt.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, replace
from urllib.parse import urljoin

from .fetcher import ScopedFetcher

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RobotsInfo:
    """What ``/robots.txt`` said for the user-agent we identify as.

    ``status`` is None when nothing was fetched at all (blocked by scope, dry
    run, or a transport error), 200 when parsed, and the response code when the
    host answered something other than a normal robots.txt.
    """

    url: str = ""
    status: int | None = None
    disallowed: tuple[str, ...] = ()
    allowed: tuple[str, ...] = ()
    sitemaps: tuple[str, ...] = ()
    error: str | None = None

    @property
    def fetched(self) -> bool:
        """True when the host actually returned a body we could parse."""
        return self.status == 200


@dataclass
class _Group:
    """One user-agent group: the agents it names and the rules under it."""

    agents: list[str] = field(default_factory=list)
    disallow: list[str] = field(default_factory=list)
    allow: list[str] = field(default_factory=list)


def parse_robots(text: str, user_agent: str = "*") -> RobotsInfo:
    """Parse *text* and return the rules that apply to *user_agent*.

    Paths are returned exactly as written — wildcards (``*``, ``$``) are left
    alone rather than pattern-matched, because nothing here gates a fetch.
    """
    groups = _parse_groups(text)
    selected = _select_group(groups, user_agent)
    sitemaps = _parse_sitemaps(text)

    if selected is None:
        return RobotsInfo(sitemaps=sitemaps)
    return RobotsInfo(
        disallowed=tuple(selected.disallow),
        allowed=tuple(selected.allow),
        sitemaps=sitemaps,
    )


async def fetch_robots(
    fetcher: ScopedFetcher, base_url: str, user_agent: str = "*"
) -> RobotsInfo:
    """Fetch and parse ``/robots.txt`` for the host of *base_url*.

    Never raises: a blocked, skipped or failed fetch comes back as a
    ``RobotsInfo`` with ``status is None``.  The scoped fetcher logs the reason
    (out-of-scope, dry-run, transport error) when it drops the request.
    """
    robots_url = urljoin(base_url, "/robots.txt")
    response = await fetcher.get(robots_url)

    if response is None:
        return RobotsInfo(url=robots_url, error="not fetched (blocked, dry-run, or fetch error)")

    if response.status_code != 200:
        logger.info("ROBOTS %s -> no robots.txt (HTTP %d)", robots_url, response.status_code)
        return RobotsInfo(url=robots_url, status=response.status_code)

    info = replace(parse_robots(response.text, user_agent), url=robots_url, status=200)
    _log_findings(info)
    return info


def _log_findings(info: RobotsInfo) -> None:
    """Log robots.txt contents as informational recon signal."""
    logger.info(
        "ROBOTS %s -> %d disallowed, %d allowed, %d sitemap(s)",
        info.url,
        len(info.disallowed),
        len(info.allowed),
        len(info.sitemaps),
    )
    for path in info.disallowed:
        # Not a boundary — a lead.  These are the paths worth looking at.
        logger.info("ROBOTS-CANDIDATE %s — disallowed path %s", info.url, path)
    for sitemap in info.sitemaps:
        logger.info("ROBOTS-SITEMAP %s — %s", info.url, sitemap)


def _parse_groups(text: str) -> list[_Group]:
    """Split *text* into user-agent groups, honouring comments and blanks."""
    groups: list[_Group] = []
    current: _Group | None = None

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        name, _, value = line.partition(":")
        name = name.strip().lower()
        value = value.strip()

        if name == "user-agent":
            # A User-agent line only opens a group when the previous one
            # already has rules; consecutive lines name agents of one group.
            if current is None or current.disallow or current.allow:
                current = _Group()
                groups.append(current)
            if value:
                current.agents.append(value.lower())
        elif name in ("disallow", "allow"):
            # Rules before any User-agent line are malformed; ignore them.
            if current is None or not value:
                continue
            target = current.disallow if name == "disallow" else current.allow
            target.append(value)

    return groups


def _select_group(groups: list[_Group], user_agent: str) -> _Group | None:
    """Return the group naming *user_agent*, else the ``*`` group, else None."""
    wanted = user_agent.lower()
    for group in groups:
        if wanted in group.agents:
            return group
    for group in groups:
        if "*" in group.agents:
            return group
    return None


def _parse_sitemaps(text: str) -> tuple[str, ...]:
    """Collect ``Sitemap:`` lines, which are not scoped to a user-agent group."""
    sitemaps = []
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        name, _, value = line.partition(":")
        if name.strip().lower() == "sitemap" and value.strip():
            sitemaps.append(value.strip())
    return tuple(sitemaps)
