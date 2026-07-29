# Options Chain Scanner

Independent, minimal repo: downloads the daily options chain (PCR, OI, IV
per strike) for a given universe (default: S&P500) and archives it as
date-partitioned Parquet. No dependency on the Mean-Reversion scanner or
on any database — only `pandas`, `numpy`, `yfinance`, `requests`.

## Files

```
ticker_provider.py               → current universe list (Wikipedia scrape, cached)
options_scanner.py                → downloads the options chain (PCR/OI/IV)
options_archive.py                → archives the full chain to Parquet
OptionsScanner_Standalone.ipynb   → interactive entry point
```

## Quick start

```bash
pip install -r requirements.txt
jupyter notebook OptionsScanner_Standalone.ipynb
```

## Why a separate repo from the MR scanner?

An options chain snapshot is unrecoverable data: once the day passes, there
is no source — free or paid — that reconstructs it retroactively. This repo
exists to run daily (e.g. via a GitHub Actions cron job) without depending
on the heavier MR pipeline (database, OHLCV download, point-in-time
membership) — if one breaks, the other keeps running normally.

The output folder (`options_archive/`) is the format the main MR script
later consumes.
