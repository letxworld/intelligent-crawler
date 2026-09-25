"""CLI entry point for the intelligent crawler."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from .engine import Crawler, CrawlReport
from .fetcher import ScopedFetcher
from .logging_config import setup_logging
from .rate_limiter import RateLimiter
from .scope_config import ScopeConfig

logger = logging.getLogger(__name__)


def cmd_crawl(args: argparse.Namespace) -> int:
    """Execute the crawl subcommand."""
    config = ScopeConfig.from_yaml(Path(args.scope))
    setup_logging(verbose=args.verbose)
    if args.dry_run:
        config.dry_run = True

    rate_limiter = RateLimiter(global_rate=config.rate_limit, per_host_rate=config.rate_limit)
    fetcher = ScopedFetcher(config=config, rate_limiter=rate_limiter)
    crawler = Crawler(
        config,
        fetcher=fetcher,
        max_concurrency=args.concurrency,
        per_host_concurrency=args.per_host_concurrency,
    )

    async def run() -> CrawlReport:
        try:
            return await crawler.crawl(args.urls)
        finally:
            await fetcher.close()

    report = asyncio.run(run())
    print_report(report)
    return 0


def print_report(report: CrawlReport) -> None:
    """Print the human-readable crawl summary."""
    print(
        f"\nCrawled {report.fetched} URL(s), skipped {report.skipped}, "
        f"{report.html_pages} HTML page(s) parsed in {report.duration:.1f}s"
    )
    for page in sorted(report.pages, key=lambda p: (p.depth, p.url)):
        status = page.status if page.status is not None else "skipped"
        line = f"  [{status}] d{page.depth} {page.url}"
        if page.is_html:
            line += f" — {page.links_found} link(s), {page.links_queued} new"
        print(line)

    candidates = report.robots_candidates
    if candidates:
        print("\nrobots.txt candidates (informational, never a boundary):")
        for robots_url, path in sorted(candidates):
            print(f"  {path}  (from {robots_url})")


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate a scope config file without making any requests."""
    try:
        config = ScopeConfig.from_yaml(Path(args.scope))
        print(f"Scope OK: {len(config.allowed_domains)} domains, dry_run={config.dry_run}")
        return 0
    except ValueError as exc:
        print(f"Scope error: {exc}", file=sys.stderr)
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(prog="crawler", description="Intelligent web crawler for authorized recon")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug output")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_crawl = subparsers.add_parser("crawl", help="Run a scoped crawl")
    p_crawl.add_argument("-s", "--scope", required=True, help="Path to scope.yaml")
    p_crawl.add_argument("--dry-run", action="store_true", help="Parse scope but don't fetch")
    p_crawl.add_argument(
        "--concurrency", type=int, default=8, help="Max requests in flight overall (default 8)"
    )
    p_crawl.add_argument(
        "--per-host-concurrency",
        type=int,
        default=4,
        help="Max requests in flight per host (default 4)",
    )
    p_crawl.add_argument("urls", nargs="+", help="Seed URLs to crawl")
    p_crawl.set_defaults(func=cmd_crawl)

    p_val = subparsers.add_parser("validate", help="Validate a scope config")
    p_val.add_argument("-s", "--scope", required=True, help="Path to scope.yaml")
    p_val.set_defaults(func=cmd_validate)

    args = parser.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
