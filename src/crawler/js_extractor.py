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

# Matches: fetch("/api/x"), fetch(`/api/${id}`), fetch("/path", opts)
FETCH_PATTERN = re.compile(
    r"""fetch\s*\(\s*([`"'])(/[^`"'()]+)\1""",
    re.IGNORECASE | re.VERBOSE,
)

# Matches: axios.get("/x"), axios.post("/x"), axios("/x"), apiClient.get("/x")
AXIOS_PATTERN = re.compile(
    r"""(?:axios|apiClient|httpClient)(?:\s*\.\s*(?:get|post|put|delete|patch|head|options))?\s*\(\s*["'](/[^"'()]+)["']""",
    re.IGNORECASE,
)

# Matches: xhr.open("GET", "/path"), new XMLHttpRequest()
XHR_PATTERN = re.compile(
    r"""(?:new\s+)?XMLHttpRequest|xhr\.open\s*\(\s*["'][A-Z]+["']\s*,\s*["'](/[^"'()]+)["']""",
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


@dataclass
class FetchPattern:
    """One transport call found in JS source."""

    path: str  # normalized path, template params replaced with {param}
    full_url: str  # the exact string from the source
    transport: str  # "fetch", "axios", or "xhr"
    line_number: int = 0


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


def extract_fetch_patterns(js_source: str) -> list[FetchPattern]:
    """Extract fetch/axios/XHR patterns from JS source."""
    results: list[FetchPattern] = []

    for m in FETCH_PATTERN.finditer(js_source):
        full_url = m.group(2)
        path = _strip_query(_normalize_path_for_template(full_url))
        results.append(FetchPattern(path=path, full_url=full_url, transport="fetch"))

    for m in AXIOS_PATTERN.finditer(js_source):
        full_url = m.group(1)
        path = _strip_query(_normalize_path_for_template(full_url))
        results.append(FetchPattern(path=path, full_url=full_url, transport="axios"))

    for m in XHR_PATTERN.finditer(js_source):
        full_url = m.group(1)
        path = _strip_query(_normalize_path_for_template(full_url))
        results.append(FetchPattern(path=path, full_url=full_url, transport="xhr"))

    # Deduplicate by (path, transport) pair.
    seen: set[tuple[str, str]] = set()
    unique: list[FetchPattern] = []
    for r in results:
        key = (r.path, r.transport)
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return unique


def _strip_query(path: str) -> str:
    """Strip query string from a path."""
    return path.split("?", 1)[0]


def _normalize_path_for_template(path: str) -> str:
    """Replace template literal segments with {param} placeholders."""
    path = re.sub(r"\$\{[a-zA-Z_][a-zA-Z0-9_]*\}", "{param}", path)
    path = re.sub(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}", "{param}", path)
    return path.rstrip("/")