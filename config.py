import os

SUBREDDITS = ["stocks", "ValueInvesting"]
BASKET_SIZE = 10
WEIGHT = 1.0 / BASKET_SIZE

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_DIR = os.path.join(BASE_DIR, "data", "history")
TICKERS_FILE = os.path.join(BASE_DIR, "data", "tickers.csv")
BLACKLIST_FILE = os.path.join(BASE_DIR, "data", "blacklist.txt")

PULLPUSH_BASE_URL = "https://api.pullpush.io/reddit/search"
REDDIT_BASE_URL = "https://old.reddit.com"
USER_AGENT = "Mozilla/5.0 (compatible; reddit-ticker-basket/1.0; +https://github.com/UpsidePotential/reddit-ticker-basket)"

RATE_LIMIT_DELAY = 1.0  # seconds between pullpush requests
REDDIT_RATE_LIMIT_DELAY = 1.0  # seconds between reddit requests
