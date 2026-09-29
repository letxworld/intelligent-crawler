"""Tests for JS static analysis — URL/path extraction."""

from __future__ import annotations

import pytest

from crawler.js_extractor import (
    JSExtractionResult,
    PATH_PATTERN,
    extract_js_paths,
    extract_paths_from_js_content,
    is_api_path,
    js_filename_to_source_map_url,
)


class TestPathPattern:
    def test_matches_api_paths(self) -> None:
        # Path pattern matches quoted / paths
        assert PATH_PATTERN.search('"/api/v1/users"')
        assert PATH_PATTERN.search("'/graphql'")

    def test_matches_asset_refs(self) -> None:
        assert PATH_PATTERN.search('"/static/app.js"')
        assert PATH_PATTERN.search('"/images/logo.png"')

    def test_does_not_match_plain_strings(self) -> None:
        assert PATH_PATTERN.search('"hello world"') is None


class TestExtractJsPaths:
    def test_empty_source(self) -> None:
        result = extract_js_paths("")
        assert result.paths == []
        assert result.api_candidates == []
        assert result.router_paths == []

    def test_single_path(self) -> None:
        result = extract_js_paths('const url = "/api/v1/users"')
        assert "/api/v1/users" in result.paths
        assert "/api/v1/users" in result.api_candidates

    def test_multiple_paths(self) -> None:
        source = '"/api/v1/users"\n"/static/app.js"\n"/graphql"\n"/images/logo.png"'
        result = extract_js_paths(source)
        assert "/api/v1/users" in result.paths
        assert "/graphql" in result.paths
        assert "/static/app.js" in result.paths
        assert "/images/logo.png" in result.paths

    def test_deduplication(self) -> None:
        source = '"/api/x"\n"/api/x"\n"/api/y"'
        result = extract_js_paths(source)
        assert result.paths.count("/api/x") == 1
        assert result.paths.count("/api/y") == 1

    def test_source_url_recorded(self) -> None:
        result = extract_js_paths('"/api/x"', "https://app.example.com/static/bundle.js")
        assert result.source_url == "https://app.example.com/static/bundle.js"

    def test_inline_script_flag(self) -> None:
        result = extract_paths_from_js_content('fetch("/api/x")', "page.html", inline=True)
        assert result.inline_script is True
        assert result.paths == ["/api/x"]


class TestIsApiPath:
    def test_api_paths(self) -> None:
        for p in ["/api/v1", "/graphql", "/v2/search", "/auth/login", "/rest/products"]:
            assert is_api_path(p)

    def test_non_api_paths(self) -> None:
        for p in ["/static/app.js", "/images/logo.png", "/about", "/"]:
            assert not is_api_path(p)


class TestJsFilenameToSourceMapUrl:
    def test_js_to_map(self) -> None:
        assert js_filename_to_source_map_url("/static/app.js") == "/static/app.js.map"

    def test_no_js_extension(self) -> None:
        assert js_filename_to_source_map_url("/static/bundle") == "/static/bundle.map"

    def test_root_js(self) -> None:
        assert js_filename_to_source_map_url("/app.js") == "/app.js.map"

    def test_with_query(self) -> None:
        assert js_filename_to_source_map_url("/static/app.js?v=1") == "/static/app.js.map"
