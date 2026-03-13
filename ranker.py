"""
Ticker ranking.

Counts total ticker mentions across a list of text strings and returns
the top N tickers sorted by mention count.
"""

import logging
from collections import Counter

from extractor import extract_tickers

logger = logging.getLogger(__name__)


def rank_tickers(texts: list[str], top_n: int = 10) -> list[tuple[str, int]]:
    """
    Extract tickers from all texts, count mentions, and return top N.

    Args:
        texts: List of text strings (post titles, selftexts, comment bodies).
        top_n: Number of top tickers to return.

    Returns:
        List of (ticker, count) tuples sorted by count descending.
    """
    counter: Counter = Counter()

    for text in texts:
        tickers = extract_tickers(text)
        counter.update(tickers)

    top = counter.most_common(top_n)
    logger.info("Top %d tickers: %s", top_n, top)
    return top
