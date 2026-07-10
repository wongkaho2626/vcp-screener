# VCP Screener & 10-Year Backtest

Screen S&P 500 / Russell 2000 stocks for **Mark Minervini's Volatility
Contraction Pattern (VCP)** and backtest the pattern over the last 10 years.

Identifies Stage 2 uptrend stocks forming tight bases with contracting
volatility near breakout pivot points, and lets you study how those setups
resolved historically (breakout / stop-hit / timeout) across a whole universe.

Data source: Yahoo Finance via `yfinance` — **no API key required** — or a
local OHLCV CSV for fully offline runs (see [Offline mode](#offline-mode)).

## Research findings (read this first)

Roughly 1,500 simulated trades across S&P 500 and Russell 2000, 2016–2026,
with fold splits, outlier trims, cost sweeps and cross-universe replication.
The honest summary:

**The pattern itself carries no market-relative alpha.** Mean excess vs SPY
is statistically zero (or negative after costs) on every dataset — point-in-time
S&P +0.04%/trade (t 0.05), offline-CSV S&P −0.53%, Russell 2000 −0.45%
(−1.05%, t −2.11 at 30 bps costs). The headline raw-return significance is
market beta, not stock selection. Rescue attempts that all failed: detection
gates (trend/RS/score/volume), a 108-combo parameter grid, a hard
trend-template prerequisite, switching to small caps, the M.E.T.A. multi-edge
framework, and every exit family below. Treat the screener as a **candidate
list generator, not a buy signal**.

**Exits: the boring baseline wins.** Initial hard stop at
max(final-contraction low, entry −8%) plus a 60-bar time exit was never
robustly beaten: 8–45% trails, ATR×2–5 trails, profit targets (15–25%, 4R),
MA10/20/50-break "sell into weakness" (significantly harmful on small caps),
the strict 3-tier scale-out framework, laggard-culling and winner-riding all
land at zero or worse ([`exit_experiment.py`](scripts/exit_experiment.py),
[`exit_stress_experiments.py`](scripts/exit_stress_experiments.py)). Removing
the time exit turns the ledger into a survivorship lottery.

**Two execution-layer findings did survive validation** (both time folds,
outlier trims, cross-universe direction):

1. **MA20 pullback entry** — don't chase the breakout close; wait up to 15
   bars for the first low-touches-MA20-and-close-holds bar. +1.36 pp paired
   vs breakout entry on the same patterns (t 3.13, S&P; +2.18 pp, t 1.96 on
   R2K). The parameter surface is a smooth gradient (deeper MAs stronger,
   longer windows weaker), not a cliff
   ([`pullback_experiment.py`](scripts/pullback_experiment.py),
   [`pullback_sensitivity.py`](scripts/pullback_sensitivity.py)).
2. **Edge Rank position sizing** — a validated RS+extension cross-sectional
   score used as a size tilt (+1.01%/trade vs equal weight under practical
   constraints on the PIT dataset; universe/benchmark-sensitive, so weaker
   evidence than #1) ([`edge_rank.py`](scripts/edge_rank.py)).

Both ship with every live screen — see the Quick Scan columns below.

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

Every candidate row carries the two validated execution overlays:

| Quick Scan column | Meaning |
|---|---|
| **Edge** | Edge Rank v2 — cross-sectional 12m-RS + inverse-extension percentile within today's candidates |
| **Weight** | Suggested position size (skip Edge<30, linear in Edge, capped at 1.5× mean) |
| **Entry** | MA20 pullback-entry state: `await BO` → `wait PB n/15` → **`BUY ZONE`** (today is the touch-and-hold bar) → `PB done` / `missed` / `invalid` |

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

### Survivorship-aware universe (recommended)

Backtesting today's index members over the past is survivorship bias. Build a
point-in-time universe instead — every ticker that was an S&P 500 member at
any point in the window, including departed/delisted names:

```bash
python3 scripts/fetch_historical_members.py \
  --start 2016-07-08 --end 2026-07-08 \
  --emit-universe backtests/universe_pit_2016_2026.txt

python3 scripts/backtest_vcp.py --years 10 \
  --universe-file backtests/universe_pit_2016_2026.txt
```

Note: Yahoo has no data for many delisted tickers — those are logged as
failed/skipped, so residual survivorship bias remains (fully eliminating it
requires a survivorship-bias-free dataset like CRSP or Norgate).

## 4. Trade simulation (excess-over-SPY)

Convert a backtest's detections into Minervini-style trades and report
**excess return over SPY (same holding windows) as the primary metric**:

```bash
python3 scripts/trade_simulator.py backtests/vcp_backtest_<timestamp>.json \
  --membership-csv scripts/data/sp500_membership.csv
```

Trade rules: enter on the first close above the pivot, **skip fills more than
5% above the pivot** (`--max-extension-pct`), stop at
**max(contraction low, entry − 8%)** (`--max-risk-pct`), exit on a close below
the stop or after 60 bars (`--max-hold-bars`). The membership filter drops
detections made while the ticker was not an index member.

Outputs `vcp_trades_*.json/.md` with t-stats and bootstrap confidence
intervals for both raw and SPY-excess returns.

### Frozen portfolio validation

The pattern-level trade simulator does not model overlapping positions or a
daily-marked account. The frozen v1 validation adds conservative next-session
fills, MA20 pullback entries, causal Edge Rank sizing, cash/capacity/sector/ADV
constraints, and two-sided costs:

```bash
python3 scripts/portfolio_backtest.py backtests/csv_full/vcp_backtest_<ts>.json \
  --price-csv SP500_Historical_Data.csv --output-dir backtests/improved

python3 scripts/portfolio_robustness.py \
  backtests/improved/vcp_portfolio_<ts>_daily.csv \
  --return-column exposure_matched_excess_return --trials 180 \
  --iterations 5000 --block-size 10
```

The portfolio command emits JSON and a daily CSV containing raw, full-SPY,
and exposure-matched excess returns. Use `--commission-bps` and
`--slippage-bps` for cost stress tests. The rules and OOS contract are frozen
in [`references/frozen_strategy_v1.md`](references/frozen_strategy_v1.md).

**Optional S&P 500 breadth gate (`--min-breadth`):** skips entries taken when
market breadth (% of S&P 500 above their 200-day MA, `scripts/data/sp500_breadth_daily.csv`)
on the entry date is below the given level. This is a **risk dial, not an alpha
source** — the [breadth experiment](scripts/breadth_experiment.py) found it does
not improve market-relative excess-over-SPY (any absolute-return effect was
concentrated in two crisis-rebound years). Use it only to trim absolute-drawdown
tail trades in weak tapes:

```bash
python3 scripts/trade_simulator.py backtests/vcp_backtest_<ts>.json \
  --membership-csv scripts/data/sp500_membership.csv --min-breadth 40
```

### Backtest caveats

- Trades are close-based with no slippage/commissions and no
  position-sizing/overlap handling — pattern-level evidence, not a full
  portfolio simulation.
- Delisted tickers without Yahoo data drop out of the universe (partial
  survivorship bias; see above).
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

## Offline mode

Backtest, trade-sim and every experiment can run without touching Yahoo by
supplying a long-format OHLCV CSV (`Ticker,Date,Open,High,Low,Close,Adj
Close,Volume`, ISO dates):

```bash
# Backtest from the local CSV (uses its SPY series as the benchmark)
python3 scripts/backtest_vcp.py --csv-data SP500_Historical_Data.csv --limit 0 --years 10

# Trade-sim / experiments take --price-csv
python3 scripts/trade_simulator.py backtests/vcp_backtest_<ts>.json \
  --price-csv SP500_Historical_Data.csv
```

Check `api_stats.data_source == "csv"` in the report metadata to confirm the
run really was offline. CSV universes are current-member snapshots, i.e.
survivorship-biased — results are an optimistic ceiling.

## Experiments

Each experiment is a standalone CLI over a `vcp_trades_*.json` (or
`vcp_backtest_*.json`) report; all support `--price-csv` for offline runs and
report excess-vs-SPY with t-stats and bootstrap CIs:

| Script | Question it answers |
|---|---|
| [`gate_experiment.py`](scripts/gate_experiment.py) | Do trend/RS-rank/score/volume entry gates add OOS excess? *(No)* |
| [`exit_experiment.py`](scripts/exit_experiment.py) | Do trailing/ATR/profit-target/MA-break exits beat stop+60d? *(No)* |
| [`exit_stress_experiments.py`](scripts/exit_stress_experiments.py) | Stop-only, strict 3-tier scale-out, asymmetric cull/ride? *(No — see docstring)* |
| [`meta_experiment.py`](scripts/meta_experiment.py) | Do M.E.T.A. multi-edge entry filters help? *(Regime luck, fails folds)* |
| [`pullback_experiment.py`](scripts/pullback_experiment.py) | Breakout entry vs waiting for the pullback? *(MA20 touch wins, +1.36 pp paired)* |
| [`pullback_sensitivity.py`](scripts/pullback_sensitivity.py) | Is the MA20 rule a cliff or a smooth surface? *(Smooth gradient; MA30 strongest)* |
| [`edge_rank.py`](scripts/edge_rank.py) | Cross-sectional Edge Rank IC, tilt backtest, deployable sizing |
| [`breadth_experiment.py`](scripts/breadth_experiment.py) | Does a market-breadth gate add alpha? *(Risk dial only)* |
| [`grid_search.py`](scripts/grid_search.py) | Detection-parameter grid (108 combos; deflated Sharpe ≈ 0) |
| [`build_trade_log_page.py`](scripts/build_trade_log_page.py) | Render trades JSONs into an interactive HTML ledger |

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
