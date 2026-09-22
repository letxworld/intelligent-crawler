"""Central scope-check function — the single gate every fetch must pass through."""

from __future__ import annotations

from fnmatch import fnmatch
from typing import Tuple
from urllib.parse import urlparse

from .scope_config import ScopeConfig


def check_scope(url: str, config: ScopeConfig) -> Tuple[bool, str]:
    """Check whether a URL is within the authorized scope.

    Returns (allowed: bool, reason: str).  When allowed is False, the reason
    explains why so it can be logged.
    """
    try:
        parsed = urlparse(url)
    except Exception as exc:
        return False, f"unparseable URL: {exc}"

    if parsed.scheme not in ("http", "https"):
        return False, f"disallowed scheme: {parsed.scheme}"

    host = (parsed.hostname or "").lower()
    if not host:
        return False, "missing hostname"

    # Excluded domains take priority over allowed domains.
    if _match_domain(host, config.excluded_domains):
        return False, f"domain excluded: {host}"

    if not _match_domain(host, config.allowed_domains):
        return False, f"domain not in scope: {host}"

    # Excluded paths.
    path = parsed.path or "/"
    for pattern in config.excluded_paths:
        if fnmatch(path, pattern) or path.startswith(pattern):
            return False, f"path excluded: {path} matches {pattern}"

    return True, "in scope"


def _match_domain(host: str, patterns: list[str]) -> bool:
    """Match a host against a list of domain patterns (supports wildcards)."""
    for pattern in patterns:
        if pattern.startswith("*."):
            # Wildcard matches any subdomain of the base domain.
            base = pattern[2:]
            if host == base or host.endswith("." + base):
                return True
        elif fnmatch(host, pattern):
            return True
    return False
