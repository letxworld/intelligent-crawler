# Phase 1 Progress — Scope Enforcement

Today's goal: 10 small commits building Phase 1 (scope config + central scope-check + rate limiter).

## Planned Commits

| # | Commit | Status |
|---|--------|--------|
| 1 | Project scaffolding (pyproject.toml, src/ structure) | TODO |
| 2 | Scope config loader (YAML parsing + schema) | TODO |
| 3 | Central scope-check function (domain/wildcard/exclusion matching) | TODO |
| 4 | Rate limiter (per-host + global token bucket) | TODO |
| 5 | Scoped fetch wrapper (HTTP client gated through scope-check) | TODO |
| 6 | Logging configuration (structured logging for skips/limits) | TODO |
| 7 | CLI entry point (argparse with subcommands) | TODO |
| 8 | Unit tests for scope-check | TODO |
| 9 | Unit tests for rate limiter | TODO |
| 10 | Integration test + README update for Phase 1 | TODO |

## Build Notes

- Python 3.11+ with httpx for async HTTP
- YAML scope config: `scope.yaml`
- Central gate: `check_scope(url) -> (bool, reason)`
- Rate limiter: per-host + global token bucket
- No bypass paths — every fetch goes through scope-check
