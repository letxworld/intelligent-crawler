"""Tests for JS transport-pattern extraction (fetch / axios / XHR)."""

from __future__ import annotations

import pytest

from crawler.js_extractor import (
    FetchPattern,
    AXIOS_PATTERN,
    FETCH_PATTERN,
    XHR_PATTERN,
    extract_fetch_patterns,
)


class TestFetchPattern:
    def test_matches_fetch_call(self) -> None:
        assert FETCH_PATTERN.search('fetch("/api/users")')
        assert FETCH_PATTERN.search('fetch(`/api/${id}`)')
        assert FETCH_PATTERN.search('fetch("/graphql", {method: "POST"})')

    def test_matches_f_lowercase(self) -> None:
        assert FETCH_PATTERN.search('fetch("/x")')

    def test_no_match_on_plain_string(self) -> None:
        assert FETCH_PATTERN.search('"/api/users"') is None


class TestAxiosPattern:
    def test_matches_axios_get(self) -> None:
        assert AXIOS_PATTERN.search('axios.get("/api/x")')
        assert AXIOS_PATTERN.search('axios.post("/api/x", data)')

    def test_matches_axios_direct(self) -> None:
        assert AXIOS_PATTERN.search('axios("/api/x")')
        # axios with options object — URL is in the options, harder to catch statically.
        # We skip this pattern for now; it requires more advanced parsing.

    def test_matches_axios_instance(self) -> None:
        assert AXIOS_PATTERN.search('apiClient.get("/v1/users")')


class TestXhrPattern:
    def test_matches_xhr_open(self) -> None:
        assert XHR_PATTERN.search('xhr.open("GET", "/api/x")')
        assert XHR_PATTERN.search('xhr.open("POST", "/graphql")')

    def test_matches_new_xmlhttprequest(self) -> None:
        assert XHR_PATTERN.search('new XMLHttpRequest()')


class TestExtractFetchPatterns:
    def test_single_fetch(self) -> None:
        result = extract_fetch_patterns('fetch("/api/users")')
        assert len(result) == 1
        assert result[0].path == "/api/users"
        assert result[0].transport == "fetch"

    def test_fetch_with_query(self) -> None:
        result = extract_fetch_patterns('fetch("/api/search?q=hello")')
        assert result[0].path == "/api/search"
        assert result[0].full_url == "/api/search?q=hello"

    def test_fetch_template_literal(self) -> None:
        result = extract_fetch_patterns('fetch(`/api/${id}`)')
        assert result[0].path == "/api/{param}"

    def test_axios_get(self) -> None:
        result = extract_fetch_patterns('axios.get("/api/x")')
        assert len(result) == 1
        assert result[0].transport == "axios"

    def test_xhr(self) -> None:
        result = extract_fetch_patterns('xhr.open("GET", "/api/x")')
        assert len(result) == 1
        assert result[0].transport == "xhr"

    def test_multiple_patterns(self) -> None:
        source = '''
        fetch("/api/a")
        axios.get("/api/b")
        xhr.open("GET", "/api/c")
        '''
        result = extract_fetch_patterns(source)
        assert len(result) == 3

    def test_deduplication(self) -> None:
        source = 'fetch("/api/x")\nfetch("/api/x")'
        result = extract_fetch_patterns(source)
        assert len(result) == 1

    def test_no_matches_empty(self) -> None:
        assert extract_fetch_patterns("console.log('hello')") == []


class TestFetchPatternData:
    def test_path_only(self) -> None:
        fp = FetchPattern(path="/api/users", full_url="/api/users", transport="fetch", line_number=1)
        assert fp.path == "/api/users"

    def test_template_path(self) -> None:
        fp = FetchPattern(path="/api/{param}", full_url="/api/123", transport="fetch", line_number=1)
        assert fp.path == "/api/{param}"
