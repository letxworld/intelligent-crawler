"""DOM link extraction from headless-rendered pages.

Phase 3: after the browser has rendered a JS-heavy page, extract links from
the live DOM — these are links that the static HTML parser never saw because
they were injected by JavaScript after load.
"""

from __future__ import annotations

import logging
from typing import Sequence

from playwright.async_api import Page

from .url_utils import normalize_url, resolve_url

logger = logging.getLogger(__name__)

# Same attribute map as the static extractor — consistency between static and
# DOM extraction means the frontier doesn't need to care which path produced a
# URL.
DOM_LINK_ATTRIBUTES = {
    "a": "href",
    "area": "href",
    "form": "action",
    "link": "href",
    "iframe": "src",
    "frame": "src",
}


async def extract_dom_links(
    page: Page,
    base_url: str,
) -> list[str]:
    """Return normalized absolute links found in the page's live DOM.

    Runs after JS has had a chance to render, so this catches links that were
    injected by client-side routing, lazy-loaded components, or dynamic
    content.  Relative URLs are resolved against *base_url* (the page's
    final URL after any redirects).
    """
    try:
        elements = await page.query_selector_all(
            ",".join(f"{tag}[{attr}]" for tag, attr in DOM_LINK_ATTRIBUTES.items())
        )
    except Exception as exc:
        logger.warning("DOM-EXTRACT-ERROR on %s — %s", base_url, exc)
        return []

    raw_links: list[str] = []
    for element in elements:
        tag = (await element.evaluate("el => el.tagName.toLowerCase()")) or ""
        attr = DOM_LINK_ATTRIBUTES.get(tag)
        if attr is None:
            continue
        try:
            value = await element.get_attribute(attr)
        except Exception:
            continue
        if value:
            raw_links.append(value.strip())

    return _resolve_links(raw_links, base_url)


def _resolve_links(raw_links: Sequence[str], base_url: str) -> list[str]:
    """Resolve and normalize *raw_links* against *base_url*, dropping junk."""
    resolved: list[str] = []
    for raw in raw_links:
        if raw.startswith("#"):
            continue
        absolute = resolve_url(base_url, raw)
        if absolute:
            resolved.append(absolute)
    return resolved


async def extract_dom_links_with_text(
    page: Page,
    base_url: str,
) -> list[tuple[str, str]]:
    """Return (url, link_text) pairs from the live DOM.

    Useful when you want to know what a link *says* (e.g. "Login",
    "Download PDF") alongside where it points — sometimes the text is a
    better signal than the URL for triaging.
    """
    try:
        anchors = await page.query_selector_all("a[href]")
    except Exception as exc:
        logger.warning("DOM-TEXT-EXTRACT-ERROR on %s — %s", base_url, exc)
        return []

    results: list[tuple[str, str]] = []
    for anchor in anchors:
        try:
            href = await anchor.get_attribute("href")
            if not href or href.startswith("#"):
                continue
            text = (
                await anchor.evaluate("el => el.innerText?.trim() || el.textContent?.trim() || ''")
            ).strip()
            absolute = normalize_url(href) or resolve_url(base_url, href)
            if absolute:
                results.append((absolute, text))
        except Exception:
            continue
    return results
