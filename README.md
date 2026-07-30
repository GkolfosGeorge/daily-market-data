# Options Chain Scanner — Standalone

Independent, minimal repo: downloads the daily options chain (PCR, OI, IV
per strike) for a given universe (default: S&P500) and archives it as
date-partitioned Parquet.

Runs automatically via GitHub Actions (`.github/workflows/daily-options-archive.yml`),
Mon-Fri, and uploads the day's archive as a downloadable artifact.

## Files

```
daily_options_archive.py         → headless entry point, called by the cron job
requirements.txt                  → depends on trading-shared-data (see below)
.github/workflows/
    daily-options-archive.yml     → daily cron + manual trigger
```

## Dependency: trading-shared-data

All the actual logic (ticker universe lookup, options chain download,
archiving) lives in the `shared-data-layer` repo, installed as a package:
```
trading-shared-data @ git+https://github.com/GkolfosGeorge/shared-data-layer.git@v0.1.0
```

This repo is pinned to a specific tagged version (`@v0.1.0`), not `@main` —
deliberately, so that changes made to `shared-data-layer` for other projects
(mean-reversion, trend-following, ...) never silently affect this repo's
daily cron. Upgrading to a newer version of `trading-shared-data` here is a
one-line, deliberate change to `requirements.txt`, not something that
happens automatically.

## Quick start (local)

```bash
pip install -r requirements.txt
python daily_options_archive.py
```
