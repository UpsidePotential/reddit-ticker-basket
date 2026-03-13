"""
CLI entry point for reddit-ticker-basket.

Commands:
  backfill  — Fetch historical data from pullpush.io, process week by week
  weekly    — Fetch the current rolling 7-day window from Reddit .json API
  report    — Display the latest basket + rebalance actions
  backtest  — Run backtest over all historical weekly baskets
"""

import argparse
import logging

from config import SUBREDDITS


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def cmd_backfill(args: argparse.Namespace) -> None:
    """Fetch all historical data from pullpush.io and save weekly snapshots."""
    from fetcher.pullpush import iter_backfill_weeks
    from portfolio import generate_and_save
    from ranker import rank_tickers

    logger = logging.getLogger(__name__)
    logger.info("Starting backfill for subreddits: %s", SUBREDDITS)

    count = 0
    for date_str, texts in iter_backfill_weeks(SUBREDDITS):
        logger.info("Processing week %s (%d texts)", date_str, len(texts))
        ranked = rank_tickers(texts)
        snapshot = generate_and_save(ranked, date_str=date_str)
        logger.info("Saved snapshot for %s: %s", date_str, [e["ticker"] for e in snapshot["basket"]])
        count += 1

    logger.info("Backfill complete. Processed %d weeks.", count)


def cmd_weekly(args: argparse.Namespace) -> None:
    """Fetch the current rolling 7-day window via Pullpush.io and save snapshot."""
    import time
    from fetcher.pullpush import fetch_week_texts
    from portfolio import generate_and_save
    from ranker import rank_tickers

    logger = logging.getLogger(__name__)
    logger.info("Fetching weekly data for subreddits: %s", SUBREDDITS)

    now = int(time.time())
    start_epoch = now - 7 * 24 * 3600

    all_texts = fetch_week_texts(SUBREDDITS, start_epoch, now)

    logger.info("Total texts collected: %d", len(all_texts))
    ranked = rank_tickers(all_texts)
    snapshot = generate_and_save(ranked)
    logger.info("Weekly snapshot saved for %s", snapshot["date"])


def cmd_report(args: argparse.Namespace) -> None:
    """Display the latest basket and rebalance actions."""
    from portfolio import print_report
    print_report()


def cmd_backtest(args: argparse.Namespace) -> None:
    """Run backtest over all historical weekly baskets."""
    from backtester import run_backtest
    run_backtest()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reddit Ticker Basket — track top stock tickers from Reddit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  backfill  Fetch all historical data from pullpush.io (resumable)
  weekly    Fetch rolling 7-day data from Reddit .json API
  report    Display latest top-10 basket + rebalance actions
  backtest  Simulate historical performance vs S&P 500
        """,
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("backfill", help="Fetch all historical data from pullpush.io")
    subparsers.add_parser("weekly", help="Fetch rolling 7-day data from Reddit .json API")
    subparsers.add_parser("report", help="Display latest basket + rebalance actions")
    subparsers.add_parser("backtest", help="Run backtest over all historical baskets")

    args = parser.parse_args()
    _setup_logging(verbose=args.verbose)

    commands = {
        "backfill": cmd_backfill,
        "weekly": cmd_weekly,
        "report": cmd_report,
        "backtest": cmd_backtest,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
