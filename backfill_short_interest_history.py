"""
backfill_short_interest_history.py

One-off (or occasional) backfill of historical FINRA short interest data.
Unlike daily_short_interest_archive.py (which only needs the LATEST
settlement date), this walks backward through past settlement dates and
downloads each one that isn't already archived locally.

Run this once to seed your history; the daily cron handles new dates
going forward from there. Not meant to run on a schedule — no GitHub
Actions workflow for this one, just run it locally when you want more
history (or re-run later to extend further back).

Usage:
    python backfill_short_interest_history.py --years 5
"""

import argparse
import time
from pathlib import Path

from daily_short_interest_archive import (
    ARCHIVE_FOLDER,
    fetch_all_rows,
    save_snapshot,
    _probe_date,
)

import pandas as pd


def find_settlement_dates_in_range(years_back: int) -> list[str]:
    """
    For each month going back `years_back` years, probes a small window
    around the 15th and a window around month-end (FINRA settlement dates
    shift for weekends/holidays, so we check a few candidate days per
    window and keep the first one that actually has data).
    """
    today = pd.Timestamp.today().normalize()
    month = today.replace(day=1)
    cutoff = today - pd.DateOffset(years=years_back)
    found = []

    while month >= cutoff.replace(day=1):
        # ── Mid-month window (13th-17th) ──────────────────────────────────
        for day in range(13, 18):
            try:
                date = month.replace(day=day)
            except ValueError:
                continue
            if date > today:
                continue
            date_str = date.strftime("%Y-%m-%d")
            if _probe_date(date_str):
                found.append(date_str)
                break
            time.sleep(0.2)

        # ── End-of-month window (last 4 calendar days) ─────────────────────
        month_end = (month + pd.DateOffset(months=1)) - pd.Timedelta(days=1)
        for offset in range(0, 4):
            date = month_end - pd.Timedelta(days=offset)
            if date > today:
                continue
            date_str = date.strftime("%Y-%m-%d")
            if _probe_date(date_str):
                found.append(date_str)
                break
            time.sleep(0.2)

        month -= pd.DateOffset(months=1)

    return sorted(set(found), reverse=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--years", type=int, default=5,
        help="How many years back to backfill (FINRA retains roughly 5 years)"
    )
    args = parser.parse_args()

    print(f"🔍 Finding settlement dates over the last {args.years} years...")
    dates = find_settlement_dates_in_range(args.years)
    print(f"   Found {len(dates)} settlement dates\n")

    folder = Path(ARCHIVE_FOLDER)
    already = (
        {p.stem.replace("short_interest_", "") for p in folder.glob("short_interest_*.parquet")}
        if folder.exists() else set()
    )
    to_fetch = [d for d in dates if d not in already]

    print(f"   Already archived: {len(already)}  |  To fetch: {len(to_fetch)}")
    if not to_fetch:
        print("✅ Nothing new to backfill.")
        return

    est_minutes = len(to_fetch) * 0.5
    print(f"   Estimated time: ~{est_minutes:.0f} minutes\n")

    for i, date_str in enumerate(to_fetch, 1):
        print(f"[{i}/{len(to_fetch)}] {date_str}")
        df = fetch_all_rows(date_str)
        save_snapshot(df, date_str)
        time.sleep(1)   # a bit more polite for a large batch job

    print("\n✅ Backfill complete.")


if __name__ == "__main__":
    main()
