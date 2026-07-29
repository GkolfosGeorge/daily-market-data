"""
daily_options_archive.py

Headless entry point for automated (GitHub Actions) daily runs. Downloads
today's options chain for the configured universe and archives it to
options_archive/ as Parquet — no notebook required.
"""

from ticker_provider import get_tickers
from options_scanner import OptionsScanner

UNIVERSE = "sp500"
CACHE_FOLDER = "cache"
ARCHIVE_FOLDER = "options_archive"
MIN_DAYS_TO_EXPIRY = 7
MAX_DAYS_TO_EXPIRY = 60


def main():
    tickers = get_tickers(UNIVERSE, folder_path=CACHE_FOLDER)
    print(f"Universe: {UNIVERSE} -> {len(tickers)} tickers")

    scanner = OptionsScanner(min_days=MIN_DAYS_TO_EXPIRY, max_days=MAX_DAYS_TO_EXPIRY)
    scanner.scan(tickers)

    saved_path = scanner.save_full_chain_archive(folder_path=ARCHIVE_FOLDER)
    if saved_path is None:
        raise RuntimeError("Archive save failed or produced no data.")

    print(f"Saved: {saved_path}")


if __name__ == "__main__":
    main()
