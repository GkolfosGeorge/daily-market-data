"""
daily_short_interest_archive.py

Archives FINRA's consolidated short interest data (all exchange-listed +
OTC securities) via the public, unauthenticated Query API:
    https://api.finra.org/data/group/otcMarket/name/consolidatedShortInterest

Unlike options chain / borrow fee data, short interest is only published
twice a month (settlement dates ~15th and end-of-month, published roughly
a week later). This script is safe to run on a daily cron anyway — it
detects the latest available settlement date and skips saving if that
date's file is already archived, so most days it's a quick no-op.

No authentication needed for this endpoint (confirmed manually — plain
POST with a JSON filter body, no API key/token required).

Usage:
    python daily_short_interest_archive.py
"""

import time
from pathlib import Path

import pandas as pd
import requests

FINRA_URL       = "https://api.finra.org/data/group/otcMarket/name/consolidatedShortInterest"
ARCHIVE_FOLDER  = "short_interest_archive"
PAGE_LIMIT      = 5000   # FINRA's synchronous request max
MAX_PAGES       = 10     # safety cap (covers well over 50,000 rows)
LOOKBACK_DAYS   = 45     # how far back to probe for the latest settlement date

HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}


def _probe_date(date_str: str) -> bool:
    """Cheap check: does FINRA have any data for this settlement date?"""
    payload = {
        "compareFilters": [
            {"compareType": "EQUAL", "fieldName": "settlementDate", "fieldValue": date_str}
        ],
        "limit": 1,
    }
    r = requests.post(FINRA_URL, json=payload, headers=HEADERS, timeout=15)
    return r.status_code == 200 and bool(r.json())


def find_latest_settlement_date(lookback_days: int = LOOKBACK_DAYS) -> str:
    """
    Scans backward day-by-day from today (cheap limit=1 probes) and returns
    the most recent date that actually has published data — avoids having
    to hardcode FINRA's exact settlement/publish calendar (which shifts
    around weekends and holidays).
    """
    today = pd.Timestamp.today().normalize()
    for offset in range(lookback_days):
        date = today - pd.Timedelta(days=offset)
        date_str = date.strftime("%Y-%m-%d")
        if _probe_date(date_str):
            return date_str
    raise RuntimeError(f"No settlement date with data found in the last {lookback_days} days.")


def fetch_all_rows(settlement_date: str) -> pd.DataFrame:
    """Paginates through every row for a given settlement date."""
    rows = []
    offset = 0

    for page_num in range(MAX_PAGES):
        payload = {
            "compareFilters": [
                {"compareType": "EQUAL", "fieldName": "settlementDate", "fieldValue": settlement_date}
            ],
            "limit": PAGE_LIMIT,
            "offset": offset,
        }
        r = requests.post(FINRA_URL, json=payload, headers=HEADERS, timeout=30)

        if r.status_code == 204:
            break
        r.raise_for_status()

        page = r.json()
        if not page:
            break

        rows.extend(page)
        print(f"  page {page_num + 1}: +{len(page):,} rows (total {len(rows):,})")

        if len(page) < PAGE_LIMIT:
            break   # last page

        offset += PAGE_LIMIT
        time.sleep(0.3)

    return pd.DataFrame(rows)


def save_snapshot(df: pd.DataFrame, settlement_date: str, folder_path: str = ARCHIVE_FOLDER) -> Path | None:
    if df.empty:
        print("⚠️ No data to save.")
        return None

    folder = Path(folder_path)
    folder.mkdir(parents=True, exist_ok=True)
    file_path = folder / f"short_interest_{settlement_date}.parquet"

    if file_path.exists():
        print(f"ℹ️  Already archived: {file_path} — no new settlement date since last run.")
        return file_path

    df.to_parquet(file_path, index=False)
    size_kb = file_path.stat().st_size / 1024
    print(f"💾 Saved: {file_path}  ({len(df):,} rows, {size_kb:.0f} KB)")
    return file_path


def main():
    print("🔍 Finding latest available settlement date...")
    settlement_date = find_latest_settlement_date()
    print(f"   Latest settlement date: {settlement_date}\n")

    print(f"📥 Fetching full short interest data for {settlement_date}...")
    df = fetch_all_rows(settlement_date)
    print(f"✅ Done — {len(df):,} total rows\n")

    save_snapshot(df, settlement_date)


if __name__ == "__main__":
    main()
