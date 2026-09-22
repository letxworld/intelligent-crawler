"""Structured logging configuration."""

from __future__ import annotations

import logging
import sys


def setup_logging(verbose: bool = False) -> None:
    """Configure structured logging for the crawler."""
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    root = logging.getLogger("crawler")
    root.setLevel(level)
    root.addHandler(handler)
