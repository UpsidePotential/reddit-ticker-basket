"""
Live weekly fetch via Reddit .json API.

Fetches posts and comments from subreddits using Reddit's public .json endpoints.
Filters to only posts from the last 7 days.
"""

import logging
import time
from datetime import datetime, timezone

import requests

from config import REDDIT_BASE_URL, REDDIT_RATE_LIMIT_DELAY, USER_AGENT

logger = logging.getLogger(__name__)


def _get(url: str, params: dict | None = None, retries: int = 3) -> dict | None:
    """Make a GET request with retries and exponential backoff."""
    headers = {"User-Agent": USER_AGENT}
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=15)
            if resp.status_code == 429:
                wait = 2 ** attempt * 5
                logger.warning("Rate limited by Reddit. Sleeping %ds", wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            wait = 2 ** attempt
            logger.warning("Request error (attempt %d/%d): %s. Retrying in %ds", attempt + 1, retries, exc, wait)
            if attempt < retries - 1:
                time.sleep(wait)
    logger.error("Failed to fetch %s after %d attempts", url, retries)
    return None


def _fetch_listing(subreddit: str, sort: str, params: dict | None = None) -> list[dict]:
    """Fetch a Reddit listing endpoint (new, top, etc.) with 'after' pagination."""
    posts = []
    after = None
    base_url = f"{REDDIT_BASE_URL}/r/{subreddit}/{sort}.json"

    while True:
        req_params = {"limit": 100}
        if params:
            req_params.update(params)
        if after:
            req_params["after"] = after

        data = _get(base_url, params=req_params)
        time.sleep(REDDIT_RATE_LIMIT_DELAY)

        if not data or "data" not in data:
            break

        children = data["data"].get("children", [])
        if not children:
            break

        posts.extend(children)
        after = data["data"].get("after")
        if not after:
            break

    return posts


def _fetch_post_comments(subreddit: str, post_id: str) -> list[str]:
    """Fetch all comment bodies for a given post."""
    url = f"{REDDIT_BASE_URL}/r/{subreddit}/comments/{post_id}.json"
    data = _get(url, params={"limit": 500})
    time.sleep(REDDIT_RATE_LIMIT_DELAY)

    if not data or len(data) < 2:
        return []

    texts = []
    _extract_comment_texts(data[1]["data"].get("children", []), texts)
    return texts


def _extract_comment_texts(children: list, texts: list) -> None:
    """Recursively extract comment bodies from a listing."""
    for child in children:
        if child.get("kind") == "t1":
            body = child["data"].get("body", "")
            if body and body != "[deleted]" and body != "[removed]":
                texts.append(body)
            replies = child["data"].get("replies", "")
            if isinstance(replies, dict):
                _extract_comment_texts(replies["data"].get("children", []), texts)


def fetch_subreddit_week(subreddit: str) -> list[str]:
    """
    Fetch all posts and comments from the last 7 days for a subreddit.

    Returns a list of text strings (titles, selftexts, comment bodies).
    """
    cutoff = datetime.now(timezone.utc).timestamp() - 7 * 24 * 3600
    texts = []
    seen_ids: set[str] = set()

    logger.info("Fetching r/%s (new + top/week)...", subreddit)

    # Fetch new posts
    new_posts = _fetch_listing(subreddit, "new")
    # Fetch top posts of the week
    top_posts = _fetch_listing(subreddit, "top", params={"t": "week"})

    all_posts = new_posts + top_posts

    filtered = []
    for post in all_posts:
        if post.get("kind") != "t3":
            continue
        pdata = post["data"]
        post_id = pdata.get("id", "")
        if post_id in seen_ids:
            continue
        created = pdata.get("created_utc", 0)
        if created < cutoff:
            continue
        seen_ids.add(post_id)
        filtered.append(pdata)

    logger.info("Found %d unique posts from last 7 days in r/%s", len(filtered), subreddit)

    for pdata in filtered:
        title = pdata.get("title", "")
        selftext = pdata.get("selftext", "")
        if title:
            texts.append(title)
        if selftext and selftext not in ("[deleted]", "[removed]"):
            texts.append(selftext)

        post_id = pdata.get("id", "")
        if post_id:
            comment_texts = _fetch_post_comments(subreddit, post_id)
            texts.extend(comment_texts)
            logger.debug("Post %s: fetched %d comments", post_id, len(comment_texts))

    logger.info("Total texts from r/%s: %d", subreddit, len(texts))
    return texts
