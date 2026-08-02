"""
weekly_earnings_surprise_archive.py

Archives earnings surprise data (EPS estimate vs actual, surprise %) via
yfinance's Ticker.earnings_dates, before it ages out of yfinance's rolling
~4-quarter window (yfinance does not retain earnings history older than
that — this is genuinely a "use it or lose it, eventually" data source,
just on a quarterly rather than daily clock).

Unlike the daily archivers, this accumulates into ONE growing file
(not one-file-per-day) — each run adds only newly-reported events not
already archived (deduped on ticker + report_date), so re-running is safe
and each ticker/quarter is stored exactly once regardless of how many
times this runs before/after it's picked up.

Usage:
    python weekly_earnings_surprise_archive.py
"""

import time
from pathlib import Path

import pandas as pd
import yfinance as yf

from ticker_provider import get_tickers

UNIVERSE              = "sp500"
CACHE_FOLDER           = "cache"
ARCHIVE_FILE           = "earnings_surprise_archive/earnings_surprises.parquet"
SLEEP_BETWEEN_TICKERS  = 0.3   # seconds — yfinance rate limiting

REQUIRED_COLUMNS = {"EPS Estimate", "Reported EPS", "Surprise(%)"}


def fetch_earnings_history(ticker: str) -> pd.DataFrame:
    """
    Returns only ALREADY-REPORTED earnings events (Reported EPS not null)
    for `ticker`, from yfinance's rolling ~4-quarter window. Upcoming
    (not-yet-reported) rows are dropped — nothing to archive there yet.
    """
    try:
        df = yf.Ticker(ticker).earnings_dates
        if df is None or df.empty:
            return pd.DataFrame()

        if not REQUIRED_COLUMNS.issubset(df.columns):
            return pd.DataFrame()

        df = df.reset_index().rename(columns={df.reset_index().columns[0]: "report_date"})
        df = df[df["Reported EPS"].notna()].copy()
        if df.empty:
            return pd.DataFrame()

        df["ticker"] = ticker
        df = df.rename(columns={
            "EPS Estimate":  "eps_estimate",
            "Reported EPS":  "eps_actual",
            "Surprise(%)":   "surprise_pct",
        })
        return df[["ticker", "report_date", "eps_estimate", "eps_actual", "surprise_pct"]]

    except Exception:
        return pd.DataFrame()


def archive_earnings_surprises(tickers: list[str]) -> pd.DataFrame:
    frames = []
    errors = 0
    total = len(tickers)

    print(f"\n🔍 Earnings Surprise Archiver — {total} tickers")
    print(f"{'─'*55}\n")

    for i, ticker in enumerate(tickers, 1):
        df = fetch_earnings_history(ticker)
        if df.empty:
            errors += 1
        else:
            frames.append(df)

        if i % 25 == 0 or i == total:
            print(f"  [{i:>4}/{total}]  found={len(frames)}  no_data/errors={errors}")

        time.sleep(SLEEP_BETWEEN_TICKERS)

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)


def save_archive(new_df: pd.DataFrame, archive_path: str = ARCHIVE_FILE) -> Path | None:
    if new_df.empty:
        print("⚠️ No data fetched — nothing to save.")
        return None

    path = Path(archive_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        existing = pd.read_parquet(path)
        before = len(existing)
        combined = pd.concat([existing, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["ticker", "report_date"], keep="last")
        new_rows = len(combined) - before
    else:
        combined = new_df.drop_duplicates(subset=["ticker", "report_date"], keep="last")
        new_rows = len(combined)

    combined = combined.sort_values(["ticker", "report_date"]).reset_index(drop=True)
    combined.to_parquet(path, index=False)

    print(f"💾 Saved: {path}  ({len(combined):,} total rows, {new_rows:+,} new since last run)")
    return path


def main():
    tickers = get_tickers(UNIVERSE, folder_path=CACHE_FOLDER)
    print(f"Universe: {UNIVERSE} -> {len(tickers)} tickers")

    new_df = archive_earnings_surprises(tickers)
    save_archive(new_df)


if __name__ == "__main__":
    main()
