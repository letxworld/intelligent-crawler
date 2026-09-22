# Phase 1 Progress — Scope Enforcement

Today's goal: 10 small commits building Phase 1 (scope config + central scope-check + rate limiter).

## Planned Commits

| # | Commit | Status |
|---|--------|--------|
| 1 | Project scaffolding (pyproject.toml, src/ structure) | DONE |
| 2 | Scope config loader (YAML parsing + schema) | DONE |
| 3 | Central scope-check function (domain/wildcard/exclusion matching) | DONE |
| 4 | Rate limiter (per-host + global token bucket) | DONE |
| 5 | Scoped fetch wrapper (HTTP client gated through scope-check) | DONE |
| 6 | Logging configuration (structured logging for skips/limits) | DONE |
| 7 | CLI entry point (argparse with subcommands) | DONE |
| 8 | Unit tests for scope-check (7 tests) | DONE |
| 9 | Unit tests for rate limiter (4 tests) | DONE |
| 10 | Integration tests + README update for Phase 1 | DONE |

## Build Notes

- Python 3.11+ with httpx for async HTTP
- YAML scope config: `scope.yaml`
- Central gate: `check_scope(url) -> (bool, reason)`
- Rate limiter: per-host + global token bucket
- No bypass paths — every fetch goes through scope-check
