"""
Backtester.

Simulates historical equal-weight weekly basket performance using yfinance.
Compares vs S&P 500 (^GSPC) benchmark and outputs summary statistics.
"""

import json
import logging
import os

import pandas as pd
import yfinance as yf

from config import HISTORY_DIR, WEIGHT

logger = logging.getLogger(__name__)

BENCHMARK = "^GSPC"


def _load_all_snapshots() -> list[dict]:
    """Load all snapshots from data/history/ sorted by date ascending."""
    if not os.path.isdir(HISTORY_DIR):
        return []
    snapshots = []
    for fname in sorted(os.listdir(HISTORY_DIR)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(HISTORY_DIR, fname)
        try:
            with open(path, encoding="utf-8") as f:
                snapshots.append(json.load(f))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not load %s: %s", path, exc)
    return snapshots


def _fetch_prices(tickers: list[str], start: str, end: str) -> pd.DataFrame:
    """Fetch weekly closing prices for a list of tickers."""
    if not tickers:
        return pd.DataFrame()
    try:
        data = yf.download(tickers, start=start, end=end, interval="1wk", progress=False, auto_adjust=True)
        if isinstance(data.columns, pd.MultiIndex):
            close = data["Close"]
        else:
            close = data[["Close"]] if "Close" in data.columns else data
        return close
    except Exception as exc:
        logger.warning("Failed to fetch prices for %s: %s", tickers, exc)
        return pd.DataFrame()


def _weekly_return(prices: pd.DataFrame, tickers: list[str]) -> float:
    """
    Calculate the equal-weight portfolio return over a one-week window.
    Returns the average return across available tickers, or NaN if no data.
    """
    available = [t for t in tickers if t in prices.columns]
    if not available or len(prices) < 2:
        return float("nan")

    sub = prices[available].dropna(how="all")
    if len(sub) < 2:
        return float("nan")

    # Use first and last available prices
    start_prices = sub.iloc[0]
    end_prices = sub.iloc[-1]

    returns = (end_prices - start_prices) / start_prices
    return float(returns.mean())


def _max_drawdown(returns: list[float]) -> float:
    """Calculate maximum drawdown from a list of period returns."""
    if not returns:
        return float("nan")
    cumulative = 1.0
    peak = 1.0
    max_dd = 0.0
    for r in returns:
        if not isinstance(r, float) or r != r:  # skip NaN
            continue
        cumulative *= (1 + r)
        if cumulative > peak:
            peak = cumulative
        dd = (peak - cumulative) / peak
        if dd > max_dd:
            max_dd = dd
    return max_dd


def _sharpe_ratio(returns: list[float], risk_free_rate: float = 0.0) -> float:
    """Calculate annualized Sharpe ratio (assuming weekly returns, 52 weeks/year)."""
    clean = [r for r in returns if isinstance(r, float) and r == r]
    if len(clean) < 2:
        return float("nan")
    s = pd.Series(clean)
    mean = s.mean()
    std = s.std()
    if std == 0:
        return float("nan")
    return float((mean - risk_free_rate / 52) / std * (52 ** 0.5))


def run_backtest() -> None:
    """
    Load all historical snapshots, simulate equal-weight portfolio returns,
    compare vs S&P 500, and print a summary table.
    """
    snapshots = _load_all_snapshots()
    if len(snapshots) < 2:
        print("Not enough snapshots for backtesting (need at least 2).")
        return

    print(f"\n📈 Running backtest over {len(snapshots)} weekly snapshots...\n")

    portfolio_returns: list[float] = []
    benchmark_returns: list[float] = []
    turnover_rates: list[float] = []
    results_rows: list[dict] = []

    prev_tickers: list[str] = []

    for i, snapshot in enumerate(snapshots[:-1]):
        date_str = snapshot["date"]
        next_date = snapshots[i + 1]["date"]
        tickers = [e["ticker"] for e in snapshot["basket"]]

        # Fetch portfolio prices
        prices = _fetch_prices(tickers, start=date_str, end=next_date)
        port_return = _weekly_return(prices, tickers)

        # Fetch benchmark prices
        bench_prices = _fetch_prices([BENCHMARK], start=date_str, end=next_date)
        bench_return = _weekly_return(bench_prices, [BENCHMARK])

        # Turnover: fraction of tickers that changed vs previous week
        if prev_tickers:
            changed = len(set(tickers) ^ set(prev_tickers))
            turnover = changed / max(len(tickers), len(prev_tickers))
        else:
            turnover = 1.0

        portfolio_returns.append(port_return)
        benchmark_returns.append(bench_return)
        turnover_rates.append(turnover)
        prev_tickers = tickers

        results_rows.append({
            "date": date_str,
            "portfolio_return": f"{port_return:.2%}" if port_return == port_return else "N/A",
            "benchmark_return": f"{bench_return:.2%}" if bench_return == bench_return else "N/A",
            "turnover": f"{turnover:.1%}",
        })

    # Print weekly results table
    print(f"{'Date':<14} {'Portfolio':<12} {'S&P 500':<12} {'Turnover'}")
    print("-" * 50)
    for row in results_rows:
        print(
            f"{row['date']:<14} {row['portfolio_return']:<12} "
            f"{row['benchmark_return']:<12} {row['turnover']}"
        )

    # Summary statistics
    clean_port = [r for r in portfolio_returns if r == r]
    clean_bench = [r for r in benchmark_returns if r == r]

    if not clean_port:
        print("\nNo valid return data available.")
        return

    total_port = 1.0
    for r in clean_port:
        total_port *= (1 + r)
    total_port -= 1

    total_bench = 1.0
    for r in clean_bench:
        total_bench *= (1 + r)
    total_bench -= 1

    n_weeks = len(clean_port)
    ann_port = (1 + total_port) ** (52 / n_weeks) - 1 if n_weeks > 0 else float("nan")
    ann_bench = (1 + total_bench) ** (52 / n_weeks) - 1 if n_weeks > 0 else float("nan")

    max_dd_port = _max_drawdown(clean_port)
    max_dd_bench = _max_drawdown(clean_bench)

    sharpe_port = _sharpe_ratio(clean_port)
    sharpe_bench = _sharpe_ratio(clean_bench)

    avg_turnover = sum(turnover_rates) / len(turnover_rates) if turnover_rates else float("nan")

    print("\n" + "=" * 50)
    print("📊 Backtest Summary")
    print("=" * 50)
    print(f"{'Metric':<25} {'Portfolio':<15} {'S&P 500'}")
    print("-" * 50)
    print(f"{'Total Return':<25} {total_port:.2%}{'':<10} {total_bench:.2%}")
    print(f"{'Annualized Return':<25} {ann_port:.2%}{'':<10} {ann_bench:.2%}")
    print(f"{'Max Drawdown':<25} {max_dd_port:.2%}{'':<10} {max_dd_bench:.2%}")
    print(f"{'Sharpe Ratio':<25} {sharpe_port:.3f}{'':<10} {sharpe_bench:.3f}")
    print(f"{'Avg Weekly Turnover':<25} {avg_turnover:.1%}")
    print(f"{'Weeks Analyzed':<25} {n_weeks}")
    print("=" * 50)
    print("\n⚠️  Past performance does not guarantee future results.")
    print("   This is not financial advice.")
