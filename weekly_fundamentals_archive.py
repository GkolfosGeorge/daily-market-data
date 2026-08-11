"""
weekly_fundamentals_archive.py

Weekly headless entry point for ingesting point-in-time company
fundamentals (SEC EDGAR XBRL) into the shared Postgres database. Thin
wrapper around fundamentals.ingest_fundamentals_for_universe() from
trading-shared-data.

Company financials update quarterly, so a weekly cron comfortably
catches new filings within days of publication — no need for a daily
schedule (unlike options/short-interest).

Unlike the daily/weekly Parquet archivers in this repo, this does NOT
write a local raw file — the `fundamentals` table in Postgres already
IS the point-in-time layer (SEC EDGAR itself is the durable, immutable
raw source, always re-fetchable), so there's no separate raw-archive
step here.

Safe to re-run: fundamentals.upsert_fundamentals() is idempotent
(ON CONFLICT DO NOTHING, keyed on ticker + metric + fiscal_year +
fiscal_period + form_type) — running this twice in the same week
changes nothing the second time.

Usage:
    python weekly_fundamentals_archive.py

Requires:
    DATABASE_URL environment variable (Neon Postgres connection string)
"""

import sys

from db import get_engine
from fundamentals import ingest_fundamentals_for_universe
from ticker_provider import get_tickers

UNIVERSE = "sp500"
CACHE_FOLDER = "cache"


def main():
    tickers = get_tickers(UNIVERSE, folder_path=CACHE_FOLDER)
    print(f"Universe: {UNIVERSE} -> {len(tickers)} tickers\n")

    engine = get_engine()
    summary = ingest_fundamentals_for_universe(tickers, engine)

    ok = summary[summary["status"] == "ok"]
    total_inserted = int(ok["inserted"].sum()) if "inserted" in ok.columns else 0
    problems = summary[summary["status"] != "ok"]

    print("\n── Summary ──────────────────────────────────")
    print(summary["status"].value_counts())
    print(f"\nΣύνολο νέων rows αυτή την εβδομάδα: {total_inserted}")

    if not problems.empty:
        print("\nTickers με προβλήματα (φυσιολογικό για μεμονωμένα no_cik/no_facts):")
        print(problems.to_string(index=False))

    # Μη-μηδενικό exit code μόνο αν ΤΙΠΟΤΑ δεν πέτυχε -- σήμα προς GitHub
    # Actions ότι κάτι πήγε συστηματικά στραβά (π.χ. SEC endpoint down ή
    # DATABASE_URL λάθος), όχι για μεμονωμένα προβληματικά tickers.
    if len(ok) == 0 and len(tickers) > 0:
        print("\n❌ Κανένα ticker δεν ολοκληρώθηκε -- πιθανό συστημικό πρόβλημα.")
        sys.exit(1)


if __name__ == "__main__":
    main()
