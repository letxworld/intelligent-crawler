"""Static link extraction from plain HTML.

This is the Phase 2 extractor: enough to run a working HTML crawler.  Anything
JavaScript-driven (inline scripts, .js files, source maps, live XHR capture)
belongs to the later extraction phase and deliberately does not live here.
"""

from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin

from .url_utils import normalize_url, resolve_url

# tag -> the attribute that carries its crawlable URL
LINK_ATTRIBUTES: dict[str, str] = {
    "a": "href",
    "area": "href",
    "form": "action",
    "link": "href",
    "iframe": "src",
    "frame": "src",
}


def extract_links(html: str) -> list[str]:
    """Return the raw (possibly relative) link targets found in *html*.

    Results are in document order and duplicates are preserved — de-duplication
    is the frontier's job.
    """
    return _parse(html).links


def extract_absolute_links(html: str, base_url: str) -> list[str]:
    """Return normalized absolute links from *html*, resolved against *base_url*.

    Anything that is not a crawlable http(s) URL (mailto:, javascript:, data:,
    bare fragments, malformed hrefs) is dropped.  A ``<base href>`` in the
    document overrides *base_url* for relative links, as in a browser.
    """
    parser = _parse(html)
    base = _document_base(base_url, parser.base_href)

    resolved = []
    for raw in parser.links:
        if raw.startswith("#"):
            # Same-document reference: the target is the page we are on.
            continue
        absolute = resolve_url(base, raw)
        if absolute:
            resolved.append(absolute)
    return resolved


def _parse(html: str) -> "_LinkCollector":
    parser = _LinkCollector()
    parser.feed(html)
    parser.close()
    return parser


def _document_base(base_url: str, base_href: str | None) -> str:
    """Return the URL relative links resolve against.

    A ``<base href>`` may itself be relative (``<base href="/app/">``), so it is
    joined to *base_url* first.  A base that is not crawlable (mailto:, junk)
    is ignored in favour of the real page URL rather than poisoning every link.
    """
    if not base_href:
        return base_url
    return normalize_url(urljoin(base_url, base_href)) or base_url


class _LinkCollector(HTMLParser):
    """Collects link targets and the document's ``<base href>`` from start tags.

    Only ``handle_starttag`` is overridden: the base class routes self-closing
    tags (``<link ... />``) through it as well, so overriding
    ``handle_startendtag`` too would collect them twice.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.base_href: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "base":
            # First <base href> wins, matching browser behaviour.
            if self.base_href is None:
                self.base_href = _target_value(attrs, "href")
            return

        wanted = LINK_ATTRIBUTES.get(tag)
        if wanted is None:
            return
        value = _target_value(attrs, wanted)
        if value:
            self.links.append(value)


def _target_value(attrs: list[tuple[str, str | None]], name: str) -> str | None:
    """Return the trimmed value of attribute *name*, or None if unusable."""
    for attr_name, value in attrs:
        if attr_name.lower() == name:
            return value.strip() if value and value.strip() else None
    return None
