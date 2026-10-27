"""Command line: python -m price_alerts [--watchlist ...] [--data-dir ...] [--dry-run] [--only NAME] [-v]

The dashboard is a subcommand: python -m price_alerts ui [--port 8765] [--open]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import ConfigError, env_bool, get_api_token, load_dotenv, load_watchlist
from .fetch import HttpFetcher
from .mailer import MailtrapMailer
from .runner import run

EXIT_CONFIG, EXIT_SEND = 1, 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m price_alerts",
        description="Check product pages and email price-drop and back-in-stock alerts via Mailtrap.",
    )
    parser.add_argument("--watchlist", default="watchlist.yaml", type=Path, help="path to watchlist.yaml")
    parser.add_argument("--data-dir", default="data", type=Path, help="where state.json and history.csv live")
    parser.add_argument("--out-dir", default="out", type=Path, help="where --dry-run saves email previews")
    parser.add_argument("--dry-run", action="store_true",
                        help="fetch and evaluate, save email HTML to out/, send nothing, don't touch data/")
    parser.add_argument("--only", metavar="NAME", help="check a single item (by name or id)")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    return parser


def build_ui_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m price_alerts ui",
        description="Open the local dashboard: add products, see price graphs and check on demand.",
    )
    parser.add_argument("--watchlist", default="watchlist.yaml", type=Path, help="path to watchlist.yaml")
    parser.add_argument("--data-dir", default="data", type=Path, help="where state.json and history.csv live")
    parser.add_argument("--host", default="127.0.0.1", help="address to listen on (default: 127.0.0.1, this machine only)")
    parser.add_argument("--port", default=8765, type=int, help="port to listen on (default: 8765)")
    parser.add_argument("--open", action="store_true", dest="open_browser", help="open the dashboard in your browser")
    return parser


def ui_main(argv: list[str]) -> int:
    from .web.server import serve

    args = build_ui_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s", stream=sys.stderr)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    load_dotenv(Path(".env"))
    return serve(args.watchlist, args.data_dir, host=args.host, port=args.port, open_browser=args.open_browser)


def main(argv: list[str] | None = None) -> int:
    raw = sys.argv[1:] if argv is None else argv
    if raw and raw[0] == "ui":
        return ui_main(raw[1:])
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-7s %(message)s",
        stream=sys.stderr,
    )
    if not args.verbose:
        # httpx logs every request at INFO; keep normal output readable.
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
    log = logging.getLogger("price_alerts")

    load_dotenv(Path(".env"))
    try:
        dry_run = args.dry_run or bool(env_bool("DRY_RUN"))
        watchlist = load_watchlist(args.watchlist)
        digest_env = env_bool("DIGEST")
        digest = watchlist.settings.digest if digest_env is None else digest_env

        settings = watchlist.settings
        mailer = None
        if not dry_run:
            mailer = MailtrapMailer(get_api_token(), settings.from_email, settings.from_name)

        with HttpFetcher(
            timeout=settings.timeout_seconds,
            delay=settings.request_delay_seconds,
            respect_robots_txt=settings.respect_robots_txt,
        ) as fetcher:
            summary = run(
                watchlist,
                data_dir=args.data_dir,
                fetcher=fetcher,
                mailer=mailer,
                dry_run=dry_run,
                out_dir=args.out_dir,
                only=args.only,
                digest=digest,
            )
    except ConfigError as exc:
        log.error("Configuration error: %s", exc)
        return EXIT_CONFIG

    print(summary.format())
    if summary.exit_code == EXIT_SEND:
        log.error("Some emails could not be sent; they'll be retried on the next run.")
    return summary.exit_code
