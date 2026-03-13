"""
Portfolio management.

Generates weekly basket snapshots, computes rebalance actions (BUY/SELL/HOLD),
saves snapshots to data/history/, and prints formatted reports.
"""

import json
import logging
import os
from datetime import datetime, timezone

from config import BASKET_SIZE, HISTORY_DIR, SUBREDDITS, WEIGHT

logger = logging.getLogger(__name__)


def _latest_snapshots(n: int = 2) -> list[dict]:
    """Load the N most recent snapshots from data/history/. Returns list sorted newest first."""
    if not os.path.isdir(HISTORY_DIR):
        return []

    files = sorted(
        [f for f in os.listdir(HISTORY_DIR) if f.endswith(".json")],
        reverse=True,
    )
    snapshots = []
    for fname in files[:n]:
        path = os.path.join(HISTORY_DIR, fname)
        try:
            with open(path, encoding="utf-8") as f:
                snapshots.append(json.load(f))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not load snapshot %s: %s", path, exc)
    return snapshots


def build_snapshot(
    ranked: list[tuple[str, int]],
    date_str: str | None = None,
    prev_snapshot: dict | None = None,
) -> dict:
    """
    Build a snapshot dict from ranked (ticker, count) pairs.

    Args:
        ranked: List of (ticker, count) tuples sorted by count descending.
        date_str: Date string (YYYY-MM-DD). Defaults to today.
        prev_snapshot: Previous snapshot dict for computing rebalance actions.

    Returns:
        Snapshot dict.
    """
    if date_str is None:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    basket = []
    for rank, (ticker, mentions) in enumerate(ranked[:BASKET_SIZE], start=1):
        basket.append({
            "rank": rank,
            "ticker": ticker,
            "mentions": mentions,
            "weight": round(WEIGHT, 6),
        })

    current_tickers = {entry["ticker"] for entry in basket}

    if prev_snapshot:
        prev_tickers = {entry["ticker"] for entry in prev_snapshot.get("basket", [])}
    else:
        prev_tickers = set()

    rebalance = {
        "buy": sorted(current_tickers - prev_tickers),
        "sell": sorted(prev_tickers - current_tickers),
        "hold": sorted(current_tickers & prev_tickers),
    }

    return {
        "date": date_str,
        "subreddits": SUBREDDITS,
        "basket": basket,
        "rebalance": rebalance,
    }


def save_snapshot(snapshot: dict) -> str:
    """Save a snapshot to data/history/{date}.json. Returns the file path."""
    os.makedirs(HISTORY_DIR, exist_ok=True)
    path = os.path.join(HISTORY_DIR, f"{snapshot['date']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)
    logger.info("Saved snapshot to %s", path)
    return path


def generate_and_save(ranked: list[tuple[str, int]], date_str: str | None = None) -> dict:
    """
    Build, save, and return a snapshot. Loads the previous snapshot for rebalance diff.
    """
    recent = _latest_snapshots(n=1)
    prev = recent[0] if recent else None
    snapshot = build_snapshot(ranked, date_str=date_str, prev_snapshot=prev)
    save_snapshot(snapshot)
    return snapshot


def print_report(snapshot: dict | None = None) -> None:
    """
    Print a formatted report for the given snapshot (or the latest one).
    """
    if snapshot is None:
        recent = _latest_snapshots(n=2)
        if not recent:
            print("No snapshots found in data/history/. Run 'python main.py weekly' first.")
            return
        snapshot = recent[0]
        prev = recent[1] if len(recent) > 1 else None
        # Recompute rebalance against actual previous snapshot
        if prev:
            snapshot = build_snapshot(
                [(e["ticker"], e["mentions"]) for e in snapshot["basket"]],
                date_str=snapshot["date"],
                prev_snapshot=prev,
            )

    print("=" * 60)
    print(f"📊 Reddit Ticker Basket — {snapshot['date']}")
    print(f"   Subreddits: {', '.join('r/' + s for s in snapshot['subreddits'])}")
    print("=" * 60)
    print(f"\n{'Rank':<6} {'Ticker':<8} {'Mentions':<10} {'Weight'}")
    print("-" * 40)
    for entry in snapshot["basket"]:
        print(
            f"{entry['rank']:<6} {entry['ticker']:<8} {entry['mentions']:<10} "
            f"{entry['weight']:.1%}"
        )

    rebal = snapshot.get("rebalance", {})
    print("\n📋 Rebalance Actions:")
    buys = rebal.get("buy", [])
    sells = rebal.get("sell", [])
    holds = rebal.get("hold", [])

    if buys:
        print(f"  🟢 BUY:  {', '.join(buys)}")
    else:
        print("  🟢 BUY:  (none)")

    if sells:
        print(f"  🔴 SELL: {', '.join(sells)}")
    else:
        print("  🔴 SELL: (none)")

    if holds:
        print(f"  🟡 HOLD: {', '.join(holds)}")
    else:
        print("  🟡 HOLD: (none)")

    print("=" * 60)
