# A-Share Growth Stock Research Pipeline

An automated daily research pipeline for a fixed universe of ~25 A-share growth
stocks. It combines Minervini-style technical screening with CANSLIM-based
fundamental ranking and a market-regime check, then hands the result to a
report-generation routine.

## What it does

A GitHub Actions workflow runs every weekday at 15:30 Beijing time (30 minutes
after the close) and:

1. Pulls price data (`baostock`) and northbound-flow / sentiment data
   (`akshare`) for the universe and the CSI300 index
2. Builds a fundamental snapshot per stock — revenue growth, ROE, P/E — from
   akshare's financial APIs
3. Runs technical analysis per stock: Minervini's trend-template criteria,
   Stage 2 classification, relative strength vs. CSI300, volume pattern
4. Assesses the overall market state: CSI300 Stage 2 check, 5-day northbound
   net flow, limit-up/limit-down ratio
5. Ranks all candidates with a CANSLIM-style screener and flags any that fail
   the hard screening rules
6. Commits the resulting JSON back to `data/`, so every day's read is
   reproducible from git history

A separate prompt (`ccr_prompt.md`) reads the cached data and drafts a
Chinese-language HTML report for delivery by email.

## Structure

| Path | Purpose |
|---|---|
| `scripts/fetch_daily_data.py` | Price + info pull via baostock/akshare |
| `scripts/fundamental_snapshot.py` | Per-stock fundamentals |
| `scripts/deep_technical.py` | Minervini / Stage 2 / RS technical scoring |
| `scripts/market_state.py` | Market-wide regime check |
| `scripts/a_share_screener.py` | CANSLIM ranking + screening-rule flags |
| `data/` | Daily output, committed by CI |
| `.github/workflows/fetch_data.yml` | Scheduled run, weekdays 15:30 Beijing time |

## Stack

Python, pandas, numpy, baostock, akshare, GitHub Actions.
