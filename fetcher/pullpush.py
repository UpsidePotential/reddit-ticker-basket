"""
Historical backfill via pullpush.io API.

Fetches submissions and comments week-by-week from the earliest available data
(starting from 2020) to the present. Supports resume by checking existing snapshots.
"""

import logging
import os
import time
from datetime import datetime, timezone

import requests

from config import HISTORY_DIR, PULLPUSH_BASE_URL, RATE_LIMIT_DELAY

logger = logging.getLogger(__name__)

# Backfill start date: 2020-01-06 (first Monday of 2020)
BACKFILL_START = int(datetime(2020, 1, 6, tzinfo=timezone.utc).timestamp())


def _get(url: str, params: dict | None = None, retries: int = 3) -> dict | None:
    """Make a GET request with retries and exponential backoff."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=30)
            if resp.status_code == 429:
                wait = 2 ** attempt * 10
                logger.warning("Rate limited by pullpush. Sleeping %ds", wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            wait = 2 ** attempt * 2
            logger.warning(
                "Request error (attempt %d/%d): %s. Retrying in %ds",
                attempt + 1, retries, exc, wait,
            )
            if attempt < retries - 1:
                time.sleep(wait)
    logger.error("Failed to fetch %s after %d attempts", url, retries)
    return None


def _fetch_content(endpoint: str, subreddit: str, after: int, before: int) -> list[str]:
    """
    Fetch all submissions or comments for a subreddit in a time range.

    Uses created_utc of the last result for pagination.
    Returns a list of text strings.
    """
    texts = []
    current_after = after
    url = f"{PULLPUSH_BASE_URL}/{endpoint}/"

    while True:
        params = {
            "subreddit": subreddit,
            "after": current_after,
            "before": before,
            "size": 100,
        }
        data = _get(url, params=params)
        time.sleep(RATE_LIMIT_DELAY)

        if not data:
            break

        items = data.get("data", [])
        if not items:
            break

        for item in items:
            if endpoint == "submission":
                title = item.get("title", "")
                selftext = item.get("selftext", "")
                if title:
                    texts.append(title)
                if selftext and selftext not in ("[deleted]", "[removed]", ""):
                    texts.append(selftext)
            else:
                body = item.get("body", "")
                if body and body not in ("[deleted]", "[removed]", ""):
                    texts.append(body)

        # Paginate using the created_utc of the last item
        last_utc = items[-1].get("created_utc", 0)
        if last_utc <= current_after or len(items) < 100:
            break
        current_after = last_utc

    return texts


def _existing_snapshot_dates() -> set[str]:
    """Return the set of date strings (YYYY-MM-DD) that already have snapshots."""
    if not os.path.isdir(HISTORY_DIR):
        return set()
    dates = set()
    for fname in os.listdir(HISTORY_DIR):
        if fname.endswith(".json"):
            dates.add(fname[:-5])
    return dates


def _week_ranges(subreddits: list[str]) -> list[tuple[int, int, str]]:
    """
    Generate (start_epoch, end_epoch, date_str) tuples for each week
    from BACKFILL_START to the start of the current week.
    Skips weeks that already have snapshots.
    """
    existing = _existing_snapshot_dates()
    now = datetime.now(timezone.utc)
    # Round down to the start of the current week (Monday)
    days_since_monday = now.weekday()
    current_week_start = int(
        datetime(now.year, now.month, now.day, tzinfo=timezone.utc).timestamp()
    ) - days_since_monday * 86400

    ranges = []
    week_start = BACKFILL_START
    while week_start < current_week_start:
        week_end = week_start + 7 * 86400
        date_str = datetime.fromtimestamp(week_start, tz=timezone.utc).strftime("%Y-%m-%d")
        if date_str not in existing:
            ranges.append((week_start, week_end, date_str))
        week_start = week_end

    return ranges


def fetch_week_texts(subreddits: list[str], start_epoch: int, end_epoch: int) -> list[str]:
    """
    Fetch all submissions and comments for the given week across all subreddits.
    Returns a list of text strings.
    """
    texts = []
    for sub in subreddits:
        logger.info(
            "Backfill r/%s: %s to %s",
            sub,
            datetime.fromtimestamp(start_epoch, tz=timezone.utc).strftime("%Y-%m-%d"),
            datetime.fromtimestamp(end_epoch, tz=timezone.utc).strftime("%Y-%m-%d"),
        )
        sub_texts = _fetch_content("submission", sub, start_epoch, end_epoch)
        logger.info("  Submissions: %d texts", len(sub_texts))
        comment_texts = _fetch_content("comment", sub, start_epoch, end_epoch)
        logger.info("  Comments: %d texts", len(comment_texts))
        texts.extend(sub_texts)
        texts.extend(comment_texts)
    return texts


def iter_backfill_weeks(subreddits: list[str]):
    """
    Generator yielding (date_str, texts) for each unprocessed historical week.
    Skips weeks that already have snapshots in data/history/.
    """
    weeks = _week_ranges(subreddits)
    logger.info("Found %d weeks to backfill", len(weeks))
    for start_epoch, end_epoch, date_str in weeks:
        texts = fetch_week_texts(subreddits, start_epoch, end_epoch)
        yield date_str, texts
