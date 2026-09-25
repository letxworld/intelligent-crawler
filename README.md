# Intelligent Crawler

A CLI-based intelligent web crawler for authorized bug bounty reconnaissance.

## Phase 1 Complete: Scope Enforcement

- YAML scope config loader with validation
- Central scope-check gate (domain wildcards, excluded paths/domains)
- Per-host + global token-bucket rate limiter
- Scoped fetch wrapper (every HTTP request passes through scope-check + rate limiter)
- Structured logging for blocked/fetched/dry-run URLs

## Phase 2 Complete: Plain-HTML Crawler

- Breadth-first crawl engine over a frontier with depth limit and per-host URL caps
- URL normalization (case, default ports, fragments, query sorting, dot-segments)
- Seen-set interface with a hash-set implementation (swappable for a Bloom filter later)
- Static link extraction from `<a>`, `<area>`, `<form>`, `<link>`, `<iframe>`, `<frame>`,
  honouring `<base href>`
- robots.txt fetched and logged as informational only — never a boundary, never permission
- Concurrency bounded globally and per host, on top of the rate limiter
- `crawl` subcommand with a human-readable summary

## Install

```bash
pip install -e .
```

## Quick Start

1. Create a `scope.yaml`:

```yaml
allowed_domains:
  - "*.example.com"
  - "api.target.org"
excluded_paths:
  - "/admin/*"
  - "/debug"
excluded_domains:
  - "*.staging.example.com"
rate_limit: 10.0          # requests/sec per host (and globally)
max_depth: 3
max_urls_per_host: 500    # crawl-trap guard; 0 means unlimited
dry_run: false
```

The scope config is the **only** authorization source. Every fetch, including the
robots.txt fetch itself, goes through the same scope check and rate limiter.

2. Validate it:

```bash
python -m crawler.cli validate --scope scope.yaml
```

3. Dry-run first — parses the scope and logs what it *would* fetch, without
   sending a single request:

```bash
python -m crawler.cli crawl --scope scope.yaml --dry-run https://app.example.com
```

4. Crawl:

```bash
python -m crawler.cli crawl --scope scope.yaml https://app.example.com
```

Options:

| Flag | Default | Meaning |
|------|---------|---------|
| `--dry-run` | off | Log every fetch decision, make no requests |
| `--concurrency` | 8 | Max requests in flight across all hosts |
| `--per-host-concurrency` | 4 | Max requests in flight to one host |
| `-v`, `--verbose` | off | Debug logging (includes depth-limit skips) |

## How robots.txt is treated

robots.txt is fetched once per host and its contents are logged: disallowed paths
are surfaced as recon candidates, and sitemaps are listed. It is deliberately
*not* a boundary — a link to a disallowed path is still crawled, because the
scope config is what authorizes crawling. It is not permission either. Nothing
in robots.txt can authorize a fetch that the scope config would block.

Paths from robots.txt are reported for a human to triage rather than queued
automatically. Add them as seed URLs if you want them crawled.

## Design notes

- **One gate.** `check_scope()` is called by `ScopedFetcher.get()`, and every
  module fetches through that wrapper. There is no second HTTP client.
- **Concurrency.** The rate limiter sets the sustained pace; per-host semaphores
  cap what is in flight at any instant. Both apply to every request.
- **Dedup.** URLs are normalized before entering the frontier, so the seen-set
  cannot hold two spellings of one page. `SeenSet` is an interface — swap the
  hash set for a Bloom filter or Redis when the crawl outgrows memory.
- **Skips are logged.** Out-of-scope URLs, depth-limit hits and host-cap hits all
  produce log lines with a reason. Nothing is dropped silently.

## Tests

```bash
pytest tests/ -v
```

The engine tests run a real `ScopedFetcher` over an `httpx.MockTransport`, so the
scope gate, robots handling and crawl loop are exercised end to end without a socket.

## License

MIT
