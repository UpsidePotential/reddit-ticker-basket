"""
Ticker extraction and validation.

Extracts stock ticker symbols from text using regex patterns,
validates them against a known ticker list, and filters out
common false positives using a blacklist.
"""

import logging
import re

from config import BLACKLIST_FILE, TICKERS_FILE

logger = logging.getLogger(__name__)

# Regex patterns for ticker extraction
_DOLLAR_PATTERN = re.compile(r'\$([A-Z]{1,5})\b')
_BARE_PATTERN = re.compile(r'\b([A-Z]{2,5})\b')

# Cached sets (loaded once)
_ticker_set: set[str] | None = None
_blacklist_set: set[str] | None = None


def _load_tickers() -> set[str]:
    """Load valid tickers from tickers.csv. Returns a set of ticker symbols."""
    global _ticker_set
    if _ticker_set is not None:
        return _ticker_set

    tickers: set[str] = set()
    try:
        with open(TICKERS_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("ticker"):
                    continue
                parts = line.split(",")
                if parts:
                    tickers.add(parts[0].strip().upper())
    except FileNotFoundError:
        logger.warning("Tickers file not found: %s", TICKERS_FILE)

    _ticker_set = tickers
    logger.debug("Loaded %d valid tickers", len(tickers))
    return _ticker_set


def _load_blacklist() -> set[str]:
    """Load blacklisted words from blacklist.txt."""
    global _blacklist_set
    if _blacklist_set is not None:
        return _blacklist_set

    blacklist: set[str] = set()
    try:
        with open(BLACKLIST_FILE, encoding="utf-8") as f:
            for line in f:
                word = line.strip().upper()
                if word:
                    blacklist.add(word)
    except FileNotFoundError:
        logger.warning("Blacklist file not found: %s", BLACKLIST_FILE)

    _blacklist_set = blacklist
    logger.debug("Loaded %d blacklisted words", len(blacklist))
    return _blacklist_set


def extract_tickers(text: str) -> list[str]:
    """
    Extract valid ticker symbols from a text string.

    Matches $TICKER patterns first (high confidence), then bare uppercase
    words (2-5 chars). Validates against the ticker list and filters blacklist.

    Returns a list of ticker strings found in the text.
    """
    tickers = _load_tickers()
    blacklist = _load_blacklist()

    found: list[str] = []

    # $TICKER style matches (high confidence)
    for match in _DOLLAR_PATTERN.finditer(text):
        ticker = match.group(1).upper()
        if ticker in blacklist:
            continue
        if not tickers or ticker in tickers:
            found.append(ticker)

    # Bare uppercase word matches
    dollar_matches = {m.group(1).upper() for m in _DOLLAR_PATTERN.finditer(text)}
    for match in _BARE_PATTERN.finditer(text):
        ticker = match.group(1).upper()
        if ticker in dollar_matches:
            continue  # Already captured via $ pattern
        if ticker in blacklist:
            continue
        if tickers and ticker not in tickers:
            continue
        found.append(ticker)

    return found
