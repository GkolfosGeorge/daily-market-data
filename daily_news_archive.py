"""
daily_news_archive.py

Headless entry point for automated (GitHub Actions) daily runs. Fetches
raw news for the configured universe and archives it to news_archive/ as
Parquet — no notebook required. Same shape as daily_options_archive.py.

Requires the FINNHUB_API_KEY environment variable (repo secret in CI).
"""

from ticker_provider import get_tickers
from news_scanner import NewsScanner

UNIVERSE = "sp500"
CACHE_FOLDER = "cache"
ARCHIVE_FOLDER = "news_archive"
LOOKBACK_DAYS = 3


def main():
    tickers = get_tickers(UNIVERSE, folder_path=CACHE_FOLDER)
    print(f"Universe: {UNIVERSE} -> {len(tickers)} tickers")

    scanner = NewsScanner(lookback_days=LOOKBACK_DAYS)
    scanner.scan(tickers)

    saved_path = scanner.save_daily_archive(folder_path=ARCHIVE_FOLDER)
    if saved_path is None:
        raise RuntimeError("Archive save failed or produced no data.")

    print(f"Saved: {saved_path}")


if __name__ == "__main__":
    main()
