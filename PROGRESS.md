# Progress

## Phase 1 — Scope Enforcement

Today's goal: 10 small commits building Phase 1 (scope config + central scope-check + rate limiter).

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

## Phase 2 — Plain-HTML Crawler

Goal (from goal.md): static fetcher + basic frontier/dedup + link extraction — a
working plain-HTML crawler. No JavaScript, no browser: that is Phase 3.

| # | Commit | Status |
|---|--------|--------|
| 1 | URL normalization helpers | DONE |
| 2 | Seen-set interface + hash-set implementation | DONE |
| 3 | BFS frontier with depth limit and per-host caps | DONE |
| 4 | Static HTML link extractor (`<base href>` aware) | DONE |
| 5 | robots.txt informational fetch and parser | DONE |
| 6 | Crawl engine (frontier + extractor + per-host concurrency) | DONE |
| 7 | CLI wiring for a real crawl + summary report | DONE |
| 8 | README + PROGRESS update for Phase 2 | DONE |

The milestone is met: `crawler crawl --scope scope.yaml https://host` walks a
plain-HTML site breadth-first, dedups, respects depth and per-host caps, and
keeps every request behind the scope gate.

## Build Notes

- Python 3.11+ with httpx for async HTTP
- YAML scope config: `scope.yaml`
- Central gate: `check_scope(url) -> (bool, reason)`
- Rate limiter: per-host + global token bucket
- No bypass paths — every fetch goes through scope-check
- robots.txt: informational only; the scope config is the only authorization source
- Tests use `httpx.MockTransport` so the scope gate runs for real without a socket

## Next (Phase 3)

Headless browser mode + SPA-shell detection + DOM extraction after render, with
the rate limiter and per-host concurrency still enforced in browser mode.
