# 📊 Reddit Ticker Basket

A Python tool that scrapes Reddit's finance subreddits, extracts stock ticker mentions, builds a weekly top-10 basket, tracks rebalance actions, and backtests historical performance — all automated via GitHub Actions.

## What It Does

1. **Scrapes** `r/stocks` and `r/ValueInvesting` for post titles, body text, and comments
2. **Extracts** stock ticker symbols using regex (`$AAPL` style and bare uppercase words)
3. **Validates** tickers against a curated list of 500+ US stocks (NYSE + NASDAQ)
4. **Ranks** tickers by total mention count across both subreddits
5. **Builds** a top-10 equal-weight basket each week
6. **Tracks** rebalance actions: BUY (new entrants), SELL (dropped out), HOLD (remained)
7. **Backtests** historical basket performance vs S&P 500 using `yfinance`
8. **Runs automatically** every morning at 6am EST via GitHub Actions

---

## Architecture

```
reddit-ticker-basket/
├── .github/
│   └── workflows/
│       └── daily-report.yml     # GitHub Actions daily workflow
├── main.py                      # CLI entry point
├── config.py                    # Configuration
├── fetcher/
│   ├── reddit_json.py           # Live weekly fetch via Reddit .json API
│   └── pullpush.py              # Historical backfill via pullpush.io API
├── extractor.py                 # Ticker extraction & validation
├── ranker.py                    # Count mentions, rank top N
├── portfolio.py                 # Weekly basket + rebalance actions
├── backtester.py                # Historical simulation with yfinance
├── data/
│   ├── tickers.csv              # Valid US stock tickers (500+)
│   ├── blacklist.txt            # False positive words to exclude
│   └── history/                 # Weekly snapshots (auto-generated JSON)
└── requirements.txt
```

**Data flow:**

```
Reddit .json API / pullpush.io
        │
        ▼
  fetcher/ (reddit_json.py / pullpush.py)
        │  raw text (titles, selftext, comments)
        ▼
  extractor.py
        │  validated ticker symbols
        ▼
  ranker.py
        │  (ticker, mention_count) pairs
        ▼
  portfolio.py  ──────────────────────────────► data/history/{date}.json
        │  basket + rebalance report               snapshot storage
        ▼
  backtester.py  ◄── yfinance price data
        │
        ▼
  Performance summary vs S&P 500
```

---

## Setup

**Requirements:** Python 3.9+

```bash
# Clone the repo
git clone https://github.com/UpsidePotential/reddit-ticker-basket.git
cd reddit-ticker-basket

# Install dependencies
pip install -r requirements.txt
```

---

## Usage

### Fetch current week's data

```bash
python main.py weekly
```

Fetches the rolling 7-day window of Reddit posts and comments from `r/stocks` and `r/ValueInvesting`, extracts tickers, builds the top-10 basket, and saves a snapshot to `data/history/{today}.json`.

### Generate a report

```bash
python main.py report
```

Displays the latest basket with mention counts and rebalance actions (BUY/SELL/HOLD) compared to the previous snapshot.

**Example output:**
```
============================================================
📊 Reddit Ticker Basket — 2026-03-13
   Subreddits: r/stocks, r/ValueInvesting
============================================================

Rank   Ticker   Mentions   Weight
----------------------------------------
1      NVDA     342        10.0%
2      AAPL     281        10.0%
3      TSLA     254        10.0%
4      META     198        10.0%
5      AMD      187        10.0%
6      MSFT     165        10.0%
7      AMZN     143        10.0%
8      GOOGL    121        10.0%
9      SOFI     98         10.0%
10     PLTR     87         10.0%

📋 Rebalance Actions:
  🟢 BUY:  PLTR, SOFI
  🔴 SELL: INTC, SMCI
  🟡 HOLD: AAPL, AMD, AMZN, GOOGL, META, MSFT, NVDA, TSLA
============================================================
```

### Backfill historical data

```bash
python main.py backfill
```

Fetches all available historical data from [pullpush.io](https://pullpush.io) starting from 2020-01-06, processing week by week. **Resumable** — skips weeks that already have snapshots in `data/history/`.

> ⚠️ This will take a long time (several hours) for a full backfill due to API rate limits. Let it run in a screen/tmux session.

### Run the backtester

```bash
python main.py backtest
```

Simulates the equal-weight weekly basket performance over all historical snapshots and compares vs S&P 500 (^GSPC).

**Example output:**
```
📊 Backtest Summary
==================================================
Metric                    Portfolio       S&P 500
--------------------------------------------------
Total Return              +47.3%          +38.1%
Annualized Return         +18.2%          +14.9%
Max Drawdown              -23.4%          -19.8%
Sharpe Ratio              0.847           0.721
Avg Weekly Turnover       30.0%
Weeks Analyzed            52
==================================================

⚠️  Past performance does not guarantee future results.
   This is not financial advice.
```

### Verbose logging

```bash
python main.py -v weekly
python main.py -v backfill
```

---

## GitHub Actions — Daily Automation

The workflow in `.github/workflows/daily-report.yml` runs every day at **6:00 AM EST (11:00 UTC)** — before US market open.

### What happens automatically

1. Checks out the repo
2. Installs Python 3.11 + dependencies
3. Runs `python main.py weekly` (fetches rolling 7-day Reddit data)
4. Runs `python main.py report` (generates basket + rebalance signals)
5. Commits `data/history/{date}.json` and `daily-report.txt` back to the repo

### Manual trigger

1. Go to the [Actions tab](../../actions)
2. Click **"📊 Daily Ticker Report"** in the left sidebar
3. Click **"Run workflow"** → **"Run workflow"**

### What you'll find after each run

| File | Contents |
|------|----------|
| `daily-report.txt` | Latest top-10 basket + buy/sell/hold actions |
| `data/history/{date}.json` | Full snapshot with tickers, mention counts, weights |
| Git commit history | Complete daily audit trail |

---

## How Ticker Extraction Works

1. **`$TICKER` pattern** — regex `\$([A-Z]{1,5})\b` (e.g., `$NVDA`, `$AAPL`) — high confidence
2. **Bare uppercase words** — regex `\b([A-Z]{2,5})\b` (e.g., `NVDA`, `AAPL`) — filtered against ticker list
3. **Validation** — matches are checked against `data/tickers.csv` (500+ US stocks)
4. **Blacklist** — common false positives are filtered out (`AI`, `CEO`, `FED`, `USA`, state abbreviations, etc.)

---

## How Rebalancing Works

Each week's snapshot is compared to the previous week's basket:

- **🟢 BUY** — tickers in the new basket but not in the previous one
- **🔴 SELL** — tickers in the previous basket but not in the new one
- **🟡 HOLD** — tickers that appear in both baskets

The basket is always **equal-weight** (10% per position with a 10-stock basket).

---

## Snapshot Format

```json
{
  "date": "2026-03-13",
  "subreddits": ["stocks", "ValueInvesting"],
  "basket": [
    {"rank": 1, "ticker": "NVDA", "mentions": 342, "weight": 0.1},
    {"rank": 2, "ticker": "AAPL", "mentions": 281, "weight": 0.1}
  ],
  "rebalance": {
    "buy": ["SOFI", "META"],
    "sell": ["SMCI", "INTC"],
    "hold": ["NVDA", "AAPL"]
  }
}
```

---

## Target Subreddits

- [r/stocks](https://www.reddit.com/r/stocks/) — general stock market discussion
- [r/ValueInvesting](https://www.reddit.com/r/ValueInvesting/) — value investing focused

Additional subreddits can be added in `config.py`:

```python
SUBREDDITS = ["stocks", "ValueInvesting", "investing", "wallstreetbets"]
```

---

## Configuration

Edit `config.py` to customize:

```python
SUBREDDITS = ["stocks", "ValueInvesting"]  # Target subreddits
BASKET_SIZE = 10                            # Number of tickers in basket
RATE_LIMIT_DELAY = 1.0                      # Seconds between pullpush requests
REDDIT_RATE_LIMIT_DELAY = 1.0              # Seconds between Reddit requests
```

---

## Backtesting Methodology

- **Period**: All weeks with available snapshots
- **Portfolio**: Equal-weight (10% per ticker), rebalanced weekly
- **Benchmark**: S&P 500 (^GSPC via yfinance)
- **Metrics**: Total return, annualized return, max drawdown, Sharpe ratio, average weekly turnover
- **Price data**: Weekly closing prices from Yahoo Finance

---

## Limitations & Disclaimers

> ⚠️ **Not financial advice.** This tool is for research and educational purposes only. Past performance does not guarantee future results.

- **Data gaps**: pullpush.io may have incomplete historical data for some periods
- **Rate limits**: Both Reddit and pullpush.io have rate limits; the tool respects them with 1-second delays and exponential backoff
- **Survivorship bias**: The ticker list includes both active and historically active stocks; delisted tickers may not have yfinance data
- **Reddit signal quality**: High mention count ≠ good investment; Reddit discussions can be driven by hype, short squeezes, or misinformation
- **No execution costs**: The backtester does not account for brokerage commissions, slippage, or taxes
- **Weekly rebalance**: The strategy assumes you can rebalance at weekly closing prices, which may not always be practical

---

## License

MIT