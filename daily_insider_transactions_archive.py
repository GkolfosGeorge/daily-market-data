"""
daily_insider_transactions_archive.py

Archives SEC Form 4 insider transactions (non-derivative buys/sells by
officers, directors, and >10% owners) for the full fundamentals universe
(768 tickers, straight from the `companies` table — not just S&P 500).

Runs DAILY (Mon-Fri), not weekly — unlike fundamentals/earnings (inherently
quarterly-paced), Form 4 is a continuous trickle (SEC requires filing
within 2 business days of the transaction), so a daily cadence keeps the
insider-buying/selling signal close to actionable instead of going stale
for up to a week.

Template B (growing accumulator, committed to repo) — same pattern as
weekly_earnings_surprise_archive.py: ONE running parquet file, each run
adds only new transactions not already archived, deduped so re-running is
always safe.

Storage: local parquet, committed to this repo (NOT Postgres — deliberately
kept off the Neon free-tier storage budget for now; see the insider
transactions design discussion for the migration path if/when that changes).

Lookback: each run only asks the SEC for filings from the last N days
(default 7 — wider than the 1-day cron gap, as a safety net for missed
runs, weekends, and holidays, same idea as the news archiver's 3-day
window scaled up for the Mon-Fri gap).

Usage:
    python daily_insider_transactions_archive.py
    python daily_insider_transactions_archive.py --lookback-days 10
"""

import argparse
import time
from pathlib import Path

import pandas as pd

from db import get_engine
from insider_transactions import fetch_universe_with_cik, fetch_transactions_for_ticker

ARCHIVE_FILE = "insider_transactions_archive/insider_transactions.parquet"
SLEEP_BETWEEN_TICKERS = 0.1  # on top of the per-request sleeps inside insider_transactions.py

DEDUP_KEYS = ["accession_number", "insider_name", "transaction_date", "transaction_code", "transaction_index"]


def archive_insider_transactions(universe: pd.DataFrame, since_date: str) -> pd.DataFrame:
    frames = []
    errors = 0
    total = len(universe)

    print(f"\n🔍 Insider Transactions Archiver — {total} tickers, since {since_date}")
    print(f"{'─'*60}\n")

    for i, row in enumerate(universe.itertuples(index=False), 1):
        try:
            df = fetch_transactions_for_ticker(row.ticker, row.cik, since_date=since_date)
            if not df.empty:
                frames.append(df)
        except Exception as e:
            errors += 1
            print(f"  ⚠️ {row.ticker}: {e}")

        if i % 50 == 0 or i == total:
            found_rows = sum(len(f) for f in frames)
            print(f"  [{i:>4}/{total}]  tickers_with_activity={len(frames)}  rows_so_far={found_rows}  errors={errors}")

        time.sleep(SLEEP_BETWEEN_TICKERS)

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)


def save_archive(new_df: pd.DataFrame, archive_path: str = ARCHIVE_FILE) -> Path | None:
    if new_df.empty:
        print("⚠️ No new transactions fetched — nothing to save.")
        return None

    path = Path(archive_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        existing = pd.read_parquet(path)
        before = len(existing)
        combined = pd.concat([existing, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=DEDUP_KEYS, keep="last")
        new_rows = len(combined) - before
    else:
        combined = new_df.drop_duplicates(subset=DEDUP_KEYS, keep="last")
        new_rows = len(combined)

    combined = combined.sort_values(["ticker", "transaction_date"]).reset_index(drop=True)
    combined.to_parquet(path, index=False)

    print(f"💾 Saved: {path}  ({len(combined):,} total rows, {new_rows:+,} new since last run)")
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--lookback-days", type=int, default=7,
        help="How many days back to ask SEC for filings (default 7 — safety net for missed runs/weekends)"
    )
    args = parser.parse_args()

    engine = get_engine()
    universe = fetch_universe_with_cik(engine)
    print(f"Universe: fundamentals companies table -> {len(universe)} tickers with known CIK")

    since_date = (pd.Timestamp.today() - pd.Timedelta(days=args.lookback_days)).strftime("%Y-%m-%d")

    new_df = archive_insider_transactions(universe, since_date=since_date)
    save_archive(new_df)


if __name__ == "__main__":
    main()
