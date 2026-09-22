"""Unit tests for scope-check function."""

from __future__ import annotations

import pytest

from crawler.scope_check import check_scope
from crawler.scope_config import ScopeConfig


@pytest.fixture
def config() -> ScopeConfig:
    return ScopeConfig(
        allowed_domains=["*.example.com", "api.target.org"],
        excluded_paths=["/admin/*", "/debug"],
        excluded_domains=["*.staging.example.com"],
    )


def test_in_scope_domain(config: ScopeConfig) -> None:
    allowed, _ = check_scope("https://app.example.com/page", config)
    assert allowed


def test_exact_match_domain(config: ScopeConfig) -> None:
    allowed, _ = check_scope("https://api.target.org/v1/users", config)
    assert allowed


def test_out_of_scope_domain(config: ScopeConfig) -> None:
    allowed, reason = check_scope("https://evil.com/page", config)
    assert not allowed
    assert "not in scope" in reason


def test_excluded_domain(config: ScopeConfig) -> None:
    allowed, reason = check_scope("https://app.staging.example.com/page", config)
    assert not allowed
    assert "excluded" in reason


def test_excluded_path(config: ScopeConfig) -> None:
    allowed, reason = check_scope("https://app.example.com/admin/users", config)
    assert not allowed
    assert "excluded" in reason


def test_disallowed_scheme(config: ScopeConfig) -> None:
    allowed, reason = check_scope("ftp://app.example.com/file", config)
    assert not allowed
    assert "scheme" in reason


def test_missing_hostname(config: ScopeConfig) -> None:
    allowed, reason = check_scope("https:///path", config)
    assert not allowed
    assert "hostname" in reason
