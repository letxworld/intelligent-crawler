"""Static JavaScript analysis — URL-path string extraction.

Phase 4 (part 1): after fetching a .js file or inline <script>, run regex-based
static analysis to find API endpoint candidates that are invisible to the HTML
link extractor.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Match any quoted string that starts with / — broad capture, filter later.
PATH_PATTERN = re.compile(r'''["']/[\w./-]+["']''', re.IGNORECASE)

# API / version / route indicators.
API_VERSION_HINTS = re.compile(
    r"(?:^|/)(?:api|v\d|graphql|rest|ws|auth|oauth|login|logout|register|signup|reset|token|verify)",
    re.IGNORECASE,
)

ROUTER_HINT_PATTERN = re.compile(
    r"""(?:route|path|component|pathname|url)\s*[:=]\s*["'](/[^"']+)["']""",
    re.IGNORECASE,
)


@dataclass
class JSExtractionResult:
    source_url: str
    paths: list[str]
    api_candidates: list[str]
    router_paths: list[str]
    fetch_patterns: list[str]
    inline_script: bool = False


def extract_js_paths(js_source: str, source_url: str = "") -> JSExtractionResult:
    paths: list[str] = []
    api_candidates: list[str] = []
    router_paths: list[str] = []

    for m in PATH_PATTERN.finditer(js_source):
        raw = m.group(0).strip("'\"")
        if raw.startswith("/") and len(raw) > 2 and raw not in paths:
            paths.append(raw)

    for p in paths:
        if API_VERSION_HINTS.search(p):
            api_candidates.append(p)

    for m in ROUTER_HINT_PATTERN.finditer(js_source):
        rp = m.group(1).rstrip("/")
        if rp and rp not in router_paths:
            router_paths.append(rp)

    for p in router_paths:
        if p not in api_candidates:
            api_candidates.append(p)

    return JSExtractionResult(
        source_url=source_url,
        paths=paths,
        api_candidates=api_candidates,
        router_paths=router_paths,
        fetch_patterns=[],
        inline_script=False,
    )


def extract_paths_from_js_content(js_content: str, source_url: str, inline: bool = False) -> JSExtractionResult:
    result = extract_js_paths(js_content, source_url)
    result.inline_script = inline
    return result


def is_api_path(path: str) -> bool:
    return bool(API_VERSION_HINTS.search(path))


def js_filename_to_source_map_url(js_url: str) -> str:
    path_part = js_url.split("?", 1)[0].rstrip("/")
    if path_part.endswith(".js"):
        return path_part[:-3] + ".js.map"
    return js_url.rstrip("/") + ".map"
