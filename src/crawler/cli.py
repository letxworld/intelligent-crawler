"""CLI entry point for the intelligent crawler."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from .fetcher import ScopedFetcher
from .logging_config import setup_logging
from .rate_limiter import RateLimiter
from .scope_config import ScopeConfig

logger = logging.getLogger(__name__)


def cmd_crawl(args: argparse.Namespace) -> int:
    """Execute the crawl subcommand."""
    config = ScopeConfig.from_yaml(Path(args.scope))
    setup_logging(verbose=args.verbose)
    rate_limiter = RateLimiter(
        global_rate=config.rate_limit,
        per_host_rate=config.rate_limit,
    )
    fetcher = ScopedFetcher(config=config, rate_limiter=rate_limiter)

    async def run():
        try:
            if args.dry_run:
                config.dry_run = True
            for url in args.urls:
                resp = await fetcher.get(url)
                if resp:
                    print(resp.text[:500])
        finally:
            await fetcher.close()

    asyncio.run(run())
    return 0


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
    p_crawl.add_argument("urls", nargs="+", help="Seed URLs to crawl")
    p_crawl.set_defaults(func=cmd_crawl)

    p_val = subparsers.add_parser("validate", help="Validate a scope config")
    p_val.add_argument("-s", "--scope", required=True, help="Path to scope.yaml")
    p_val.set_defaults(func=cmd_validate)

    args = parser.parse_args()
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
