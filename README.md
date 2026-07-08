# VCP Screener & 10-Year Backtest

Screen S&P 500 / Russell 2000 stocks for **Mark Minervini's Volatility
Contraction Pattern (VCP)** and backtest the pattern over the last 10 years.

Identifies Stage 2 uptrend stocks forming tight bases with contracting
volatility near breakout pivot points, and lets you study how those setups
resolved historically (breakout / stop-hit / timeout) across a whole universe.

Data source: Yahoo Finance via `yfinance` — **no API key required**.

## Install

```bash
pip install -r requirements.txt
```

## 1. Screen for VCPs (today)

```bash
# Default: S&P 500, top 100 candidates
python3 scripts/screen_vcp.py --output-dir reports/

# Russell 2000 small-caps
python3 scripts/screen_vcp.py --index russell2000 --output-dir reports/

# S&P 500 + Russell 2000 combined (no candidate cap; slower)
python3 scripts/screen_vcp.py --index both --full-universe --output-dir reports/

# Custom universe
python3 scripts/screen_vcp.py --universe AAPL NVDA MSFT AMZN META --output-dir reports/

# Minervini strict mode: only valid VCPs in Pre-breakout/Breakout state
python3 scripts/screen_vcp.py --strict --output-dir reports/
```

Pipeline: **Pre-Filter** (price/volume/52w position) → **Trend Template**
(7-point Stage 2 filter) → **VCP Detection & Scoring** (contraction analysis,
volume dry-up, pivot proximity, relative strength).

Outputs timestamped `vcp_screener_*.json` and `vcp_screener_*.md` reports.

## 2. Historical scan (one ticker)

Walk a single ticker's history and find every VCP that ever formed, each
labeled with its forward outcome:

```bash
# 10 years of NVDA (2520 trading days)
python3 scripts/screen_vcp.py --history 2520 --ticker NVDA --output-dir reports/
```

## 3. Backtest (multi-ticker, 10 years)

Run the historical scanner across a whole universe and aggregate the results
into portfolio-level statistics — overall breakout/stop/timeout rates, plus
breakdowns by year, by composite-score rating band, and by ticker:

```bash
# 10-year backtest on a custom universe
python3 scripts/backtest_vcp.py --years 10 --universe AAPL NVDA MSFT AVGO LLY

# 10-year backtest on the first 50 S&P 500 snapshot names
python3 scripts/backtest_vcp.py --years 10 --index sp500 --limit 50

# Full S&P 500 (slow: ~500 history downloads)
python3 scripts/backtest_vcp.py --years 10 --index sp500 --limit 0

# Tickers from a file (one per line, '#' comments allowed)
python3 scripts/backtest_vcp.py --years 10 --universe-file tickers.txt
```

Outputs timestamped `vcp_backtest_*.json` (full detection timelines included)
and `vcp_backtest_*.md` into `backtests/`.

### Backtest caveats

- Outcomes are **pattern-level labels**, not a portfolio simulation — no
  position sizing, slippage, commissions, or overlapping-signal handling.
- Universe snapshots are **today's members applied backwards** →
  survivorship bias; treat breakout rates as optimistic upper bounds.
- Historical `marketCap` and universe-relative RS aren't reconstructable from
  OHLCV, so per-detection RS is vs SPY only.

## Tuning parameters

Both the screener and the backtest accept the same detection knobs:

| Parameter | Default | Effect |
|-----------|---------|--------|
| `--min-contractions` | 2 | Higher = fewer but higher-quality patterns |
| `--t1-depth-min` | 10.0% | Higher = excludes shallow first corrections |
| `--breakout-volume-ratio` | 1.5x | Higher = stricter volume confirmation |
| `--atr-multiplier` | 1.5 | Lower = more sensitive swing detection |
| `--contraction-ratio` | 0.70 | Lower = requires tighter contractions |
| `--min-contraction-days` | 5 | Higher = longer minimum contraction |
| `--lookback-days` | 120 | Longer = finds older patterns |

Backtest-specific: `--years` (default 10), `--stride-days` (as-of cursor step,
default 5), `--outcome-days` (forward window, default 60), `--limit`
(index-universe cap, default 50, `0` = all), `--sleep-secs` (fetch pacing).

## Refreshing index constituents

Membership snapshots live in `scripts/data/`. Refresh with:

```bash
python3 scripts/refresh_constituents.py --index both
```

## Tests

```bash
python3 -m pytest tests/ -v
```

## Docs

- `references/vcp_methodology.md` — VCP theory and the 7-point Trend Template
- `references/scoring_system.md` — composite scoring and rating bands
- `references/data_source.md` — yfinance data source and snapshot refresh

## Disclaimer

For research and education only. Nothing here is investment advice; past
pattern statistics do not predict future returns.
