# Daily Market Data

Automated, GitHub Actions-driven collection of market data that would
otherwise be lost or hard to reconstruct after the fact: options chain
snapshots, FINRA short interest, and earnings surprise history.

## What's here

```
daily_options_archive.py              → daily options chain (PCR, OI, IV per strike)
daily_short_interest_archive.py       → FINRA consolidated short interest (twice/month source)
backfill_short_interest_history.py    → one-off backfill of historical short interest (run locally)
weekly_earnings_surprise_archive.py   → EPS estimate vs actual, accumulated beyond yfinance's ~4-quarter window
requirements.txt
.github/workflows/
    daily-options-archive.yml
    daily-short-interest-archive.yml
    weekly-earnings-surprise-archive.yml
```

All three scanners rely on
[`trading-shared-data`](https://github.com/GkolfosGeorge/shared-data-layer)
(pinned to a specific tag — see `requirements.txt`) for the ticker universe
lookup. No vendored copies of shared modules live in this repo.

## Options chain archive

Runs daily (Mon-Fri), after US market close. Options chain data cannot be
reconstructed retroactively once the day passes — this is why it runs on a
tight daily schedule.

**Storage:** `options_archive/` — **not** committed to the repo (gitignored).
Each run uploads that day's snapshot as a GitHub Actions artifact
(30-day retention). Download manually and merge into local storage
periodically.

## Short interest archive

FINRA only publishes new settlement dates twice a month (mid-month and
month-end, ~1 week after each), via the free, unauthenticated
`consolidatedShortInterest` Query API. The daily script detects the latest
available settlement date and safely no-ops if nothing new has been
published; the cron itself runs twice a week (not daily) to reduce
redundant re-downloads.

**Storage:** `short_interest_archive/` — **not** committed (gitignored),
same artifact-based flow as options.

**Backfilling history:** unlike options, FINRA retains a few years of
history — run `backfill_short_interest_history.py` locally (not on a
schedule) to seed historical settlement dates before the daily/weekly cron
takes over from the latest one forward.

## Earnings surprise archive

yfinance's `Ticker.earnings_dates` only retains roughly the last 4 reported
quarters — older data silently ages out. This script runs weekly, merges
newly-reported earnings events into a single running file (deduplicated on
ticker + report date), and — critically — **commits that file back to the
repo** via the workflow's own `GITHUB_TOKEN`, so the archive actually
accumulates across runs instead of resetting on every fresh CI checkout.

**Storage:** `earnings_surprise_archive/earnings_surprises.parquet` — **is**
committed to the repo (the opposite of the two archives above — this file
*is* the permanent record, not a disposable daily snapshot).

## Manually triggering any workflow

Actions tab → select the workflow → **Run workflow**. Useful for testing
changes without waiting for the next scheduled run.
