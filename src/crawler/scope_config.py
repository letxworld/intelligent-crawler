"""Load and validate the scope configuration file (YAML)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import yaml


@dataclass
class ScopeConfig:
    """Parsed and validated scope configuration."""

    allowed_domains: List[str]
    excluded_paths: List[str] = field(default_factory=list)
    excluded_domains: List[str] = field(default_factory=list)
    rate_limit: float = 10.0
    max_depth: int = 5
    dry_run: bool = False

    @classmethod
    def from_yaml(cls, path: Path) -> "ScopeConfig":
        """Load a scope config from a YAML file."""
        raw = yaml.safe_load(path.read_text())
        if not isinstance(raw, dict):
            raise ValueError("Scope config must be a YAML mapping at the top level.")

        allowed = raw.get("allowed_domains")
        if not allowed or not isinstance(allowed, list):
            raise ValueError("scope.yaml must define 'allowed_domains' as a non-empty list.")

        return cls(
            allowed_domains=[str(d).strip().lower() for d in allowed],
            excluded_paths=[str(p) for p in raw.get("excluded_paths", [])],
            excluded_domains=[str(d).strip().lower() for d in raw.get("excluded_domains", [])],
            rate_limit=float(raw.get("rate_limit", 10.0)),
            max_depth=int(raw.get("max_depth", 5)),
            dry_run=bool(raw.get("dry_run", False)),
        )
