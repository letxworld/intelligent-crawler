"""URL normalization helpers.

The crawler only ever treats a URL as "already seen" in its normalized form, so
normalization has to be stable and lossless with respect to what we actually
request: same page, one spelling.  Everything here is pure and sync — nothing
in this module makes a request.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

ALLOWED_SCHEMES = ("http", "https")
DEFAULT_PORTS = {"http": 80, "https": 443}


def normalize_url(url: str) -> str:
    """Return the canonical spelling of *url*, or "" if it is not crawlable.

    Applies the usual canonicalisation rules: lower-cased scheme and host,
    default ports dropped, dot-segments resolved, duplicate slashes collapsed,
    fragment stripped, query parameters sorted, and an empty path turned into
    "/".  Non-http(s) URLs (mailto:, javascript:, data:, ...) return "" so
    callers can drop them without a separate scheme check.
    """
    try:
        parts = urlsplit(url.strip())
        scheme = parts.scheme.lower()
        host = (parts.hostname or "").lower()
        port = parts.port
    except ValueError:
        # Malformed URL (bad port, unbalanced IPv6 bracket, ...).
        return ""

    if scheme not in ALLOWED_SCHEMES or not host:
        return ""

    netloc = host
    if port and port != DEFAULT_PORTS[scheme]:
        netloc = f"{host}:{port}"

    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
    return urlunsplit((scheme, netloc, _normalize_path(parts.path), query, ""))


def resolve_url(base: str, target: str) -> str:
    """Resolve *target* against *base* and normalize the result.

    Returns "" for anything that is not a crawlable http(s) URL, which is how
    relative, fragment-only, mailto:, data: and javascript: links get dropped
    without the caller special-casing them.
    """
    if not target:
        return ""
    return normalize_url(urljoin(base, target.strip()))


def host_of(url: str) -> str:
    """Return the lower-cased hostname of *url*, or "" if it has none."""
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def _normalize_path(path: str) -> str:
    """Collapse duplicate slashes and resolve "." / ".." segments."""
    segments: list[str] = []
    for segment in path.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if segments:
                segments.pop()
            continue
        segments.append(segment)

    normalized = "/" + "/".join(segments)
    if path.endswith("/") and normalized != "/":
        normalized += "/"
    return normalized
