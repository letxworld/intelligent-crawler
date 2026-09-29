"""Tests for SPA-shell detection heuristic."""

from __future__ import annotations

import pytest

from crawler.browser import is_spa_shell


@pytest.mark.parametrize(
    "body, content_type, expected",
    [
        # Classic SPA shell: tiny body, script tag, HTML content type.
        (
            "<html><body><div id='root'></div><script src='app.js'></script></body></html>",
            "text/html",
            True,
        ),
        # Even tinier shell.
        ("<!DOCTYPE html><script src='/static/js/main.js'></script>", "text/html", True),
        # Enough body text to not be a shell.
        (
            "<html><body><h1>Welcome</h1><p>This is a real page with content.</p></body></html>",
            "text/html",
            False,
        ),
        # Non-HTML content type is never a shell.
        ("<html><body><script></script></body></html>", "application/javascript", False),
        # No script tag — not a JS shell.
        ("<html><body><p>tiny</p></body></html>", "text/html", False),
        # Empty body — too short but no script, so not flagged.
        ("", "text/html", False),
        # Non-HTML with enough length.
        ("console.log('hello');", "application/javascript", False),
    ],
)
def test_is_spa_shell(body: str, content_type: str, expected: bool) -> None:
    assert is_spa_shell(body, content_type) is expected
