# Intelligent Crawler

A CLI-based intelligent web crawler for authorized bug bounty reconnaissance.

## Phase 1 Complete: Scope Enforcement

### What's built

- YAML scope config loader with validation
- Central scope-check gate (domain wildcards, excluded paths/domains)
- Per-host + global token-bucket rate limiter
- Scoped fetch wrapper (every HTTP request passes through scope-check + rate limiter)
- CLI with `crawl` and `validate` subcommands
- Structured logging for blocked/fetched/dry-run URLs

### Install

```bash
pip install -e .
```

### Quick Start

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
rate_limit: 10.0
max_depth: 5
dry_run: false
```

2. Validate it:

```bash
python -m crawler.cli validate --scope scope.yaml
```

3. Crawl (dry-run first):

```bash
python -m crawler.cli crawl --scope scope.yaml --dry-run https://app.example.com
```

### Tests

```bash
pytest tests/ -v
```

## License

MIT
