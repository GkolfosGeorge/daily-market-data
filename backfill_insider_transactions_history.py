"""
backfill_insider_transactions_history.py

One-off backfill of historical Form 4 insider transactions, for the full
768-ticker fundamentals universe. Unlike weekly_insider_transactions_archive.py
(which only looks back a couple weeks), this walks each company's ENTIRE
filing history back to a cutoff date (default 3 years) and archives
everything found.

Not meant to run on a schedule — no GitHub Actions workflow for this one,
same as backfill_short_interest_history.py. Run it once locally to seed
history; the weekly cron picks up from there going forward. Safe to
re-run (dedup handles it), so also fine to extend further back later by
raising --years.

Estimated time: at ~10 req/sec SEC rate limit and roughly 1 index-lookup +
2-6 filing-fetches per active ticker, expect this to take a while for 768
tickers — the script prints progress and an ETA so you can judge whether
to run it in the background.

Usage:
    python backfill_insider_transactions_history.py --years 3
"""

import argparse
import time

import pandas as pd

from db import get_engine
from insider_transactions import fetch_universe_with_cik, fetch_transactions_for_ticker
from daily_insider_transactions_archive import save_archive, ARCHIVE_FILE


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--years", type=int, default=3,
        help="How many years back to backfill (default 3)"
    )
    parser.add_argument(
        "--start-from", type=str, default=None,
        help="Ticker to resume from (alphabetical), in case a previous run was interrupted"
    )
    args = parser.parse_args()

    engine = get_engine()
    universe = fetch_universe_with_cik(engine)
    if args.start_from:
        universe = universe[universe["ticker"] >= args.start_from].reset_index(drop=True)

    cutoff = (pd.Timestamp.today() - pd.DateOffset(years=args.years)).strftime("%Y-%m-%d")
    total = len(universe)

    print(f"🔍 Backfilling insider transactions since {cutoff}  ({total} tickers)")
    print(f"   Resume later with --start-from <TICKER> if this gets interrupted.\n")

    frames = []
    errors = 0
    start_time = time.time()

    for i, row in enumerate(universe.itertuples(index=False), 1):
        try:
            df = fetch_transactions_for_ticker(row.ticker, row.cik, since_date=cutoff)
            if not df.empty:
                frames.append(df)
        except Exception as e:
            errors += 1
            print(f"  ⚠️ {row.ticker}: {e}")

        if i % 20 == 0 or i == total:
            elapsed = time.time() - start_time
            rate = i / elapsed if elapsed > 0 else 0
            eta_min = (total - i) / rate / 60 if rate > 0 else float("nan")
            found_rows = sum(len(f) for f in frames)
            print(
                f"  [{i:>4}/{total}]  rows_so_far={found_rows}  errors={errors}  "
                f"elapsed={elapsed/60:.1f}m  eta={eta_min:.1f}m  (last: {row.ticker})"
            )

            # Save incrementally every ~20 tickers so an interruption doesn't
            # lose progress — this is a long-running job.
            if frames:
                combined = pd.concat(frames, ignore_index=True)
                save_archive(combined, ARCHIVE_FILE)
                frames = []

    if frames:
        combined = pd.concat(frames, ignore_index=True)
        save_archive(combined, ARCHIVE_FILE)

    print(f"\n✅ Backfill complete. {errors} tickers had errors.")


if __name__ == "__main__":
    main()
