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

**Beyond VCP: the signal-family test.** Three prespecified non-VCP entry
families were run on the same infrastructure (one parameterisation each, no
grids) to ask whether this tape contains any harvestable signal at all
([`signal_family_experiment.py`](scripts/signal_family_experiment.py)).
Gross of frictions, 12-1 cross-sectional momentum looked like the winner
(S&P +0.89%/mo, monthly-clustered t 3.76, fold-stable; R2K +0.81%/mo vs an
equal-weight small-cap benchmark, t 3.13); 52-week-high proximity dies
post-2021 in both universes (a third independent null for breakout-style
entries) and RSI(2) mean-reversion is too thin to survive costs. The
validation suite ([`momentum_validation.py`](scripts/momentum_validation.py))
then measured turnover (~28%/month replaced; survives a 50 bp round-trip
easily), scanned lookbacks (smooth 3-1…12-1 surface) — and applied
**point-in-time index membership, which cut the edge ~60% in both
universes**: S&P +0.88 → +0.35%/mo (t 1.79), R2K +0.81 → +0.31%/mo (t 1.23),
using `scripts/data/r2k_membership.csv` (7,079 intervals rebuilt from
quarterly IWM holdings snapshots by
[`fetch_r2k_membership.py`](scripts/fetch_r2k_membership.py)). Most of the
measured "momentum edge" was the index-inclusion effect. PIT-clean momentum
is directionally positive but statistically insignificant on survivor-only
prices — **not deployable on this evidence either**.

**Close-out (2026-07-12).** Three final declared tests shut the remaining
doors. (1) Market-regime conditioning of trade excess — SPY>200DMA and SPY
20-day realized-vol splits — is null on both universes (|Welch t| ≤ 0.83),
as the breadth gate already was; the excess-vs-SPY metric is market-neutral
by construction, so regime gates structurally can't rescue it. (2) The two
validated overlays **don't stack**: the pullback improvement does not
concentrate in high-Edge names (Edge≥70 pooled t 1.09, outlier-driven;
interaction sign flips across universes) — they repair overlapping
weaknesses ([`edge_pullback_interaction.py`](scripts/edge_pullback_interaction.py)).
(3) The frozen v1 realistic portfolio scored **20/100 — Reject** (CAGR
−0.45%, exposure-matched excess t ≈ −1.8 to −2.7, OOS Sharpe collapse; see
`backtests/improved/final_verification_report.md`). **The research programme
is closed**: the execution findings are real, the alpha is not, and any v2
requires new data and a new predeclared hypothesis.

**Post-close-out declared test (2026-07-14): support-aware screening +
industry momentum — also null.** One frozen hypothesis was run on top of the
new support/resistance overlay: take only VCP detections within 3% of a
strong support zone, then keep only names whose GICS industry is in the top
30% by 6-1 momentum (t−126 → t−21, equal-weighted, thresholds hard-coded so
the test couldn't be tuned;
[`industry_momentum_vcp_experiment.py`](scripts/industry_momentum_vcp_experiment.py)).
The gate cut trades 104 → 48 and both variants still lose in the 2021–2026
fold; exposure-matched excess t −0.48 (gated) / −0.69 (support-only), OOS
Sharpe negative for both. GICS classification is a current snapshot, not
point-in-time, so even these numbers are optimistic. Conclusion unchanged:
support/resistance zones are a **context overlay, not an alpha source**.

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
| **Support / Resistance** | Nearest active zone bounds and signed distance to its midpoint |
| **R/R** | Simple reward/risk from the nearest resistance and support midpoints; blank if either side is unavailable |
| **Entry** | MA20 pullback-entry state: `await BO` → `wait PB n/15` → **`BUY ZONE`** (today is the touch-and-hold bar) → `PB done` / `missed` / `invalid` |

### Support and resistance zones

Support and resistance are **probabilistic price zones, not guaranteed reversal
points or trading signals**. Zone enrichment is on by default for live,
historical and backtest scans. It is an additive overlay: it does not change the
existing VCP score or ranking unless you explicitly enable a support/resistance
filter.

#### Detection and look-ahead prevention

- The calculator works on a chronological copy of the daily OHLCV bars. A
  strict swing high/low needs `--sr-swing-window` lower highs/lows on both
  sides, so with the default window of 5 a swing becomes available only five
  sessions after the extreme. Historical scans never backdate that knowledge.
- Candidate points include confirmed swings, prior major highs/lows, sparse
  rolling consolidation boundaries, causally confirmed VCP contraction
  boundaries, and the three highest-volume daily closes whose volume is at
  least 1.5× the prior rolling 50-session average. The latter are a deliberately
  coarse volume-at-price proxy. Points with the same role are clustered when
  they are within
  `max(price × --sr-zone-tolerance-pct, ATR × --sr-zone-tolerance-atr)`; the
  defaults are `max(0.5% of price, 0.5 × ATR(14))`.
- Touch reaction statistics use only the following bars needed to confirm the
  swing. A zone is not searched for a break until the configured minimum
  number of touches is confirmed. Later touches update the bounds with their
  own contemporaneous ATR tolerance without rewriting an earlier event. A
  breakout is recognized only on its final confirmation close, and a
  role-reversal retest only on a later bar.
- By default, a returned zone needs at least two distinct touch dates, at least
  moderate strength, and only the nearest three active zones on either side are
  included in `support_zones`, `resistance_zones` and `zones`. `all_zones`
  retains scored zones that passed the minimum-touch rule, including zones
  below the displayed strength threshold.

Distances are signed midpoint distances from the current close: support below
price is normally negative and resistance above price positive. Potential
reward/risk is `(resistance midpoint - price) / (price - support midpoint)`;
it is `null` when either side is missing or the geometry is invalid.

#### Transparent strength score

Each zone exposes `strength_score` (0–100) and every term in
`strength_components`. The score is the capped sum:

```text
touches        = min(30, confirmed_touches / 4 × 30)
recency        = 15 × max(0, 1 - bars_since_latest_confirmation / (lookback_bars - 1))
reaction       = 20 × min(1, average_reaction_in_ATR / 3)
volume         = 10 × min(1, average_touch_volume_ratio / 1.5)
time_near_zone = 10 × min(1, closes_inside_zone / 10)
major_swing    = 10 if any contributing point is a major swing, else 0
role_reversal  = 5 if a confirmed role reversal occurred, else 0
```

Categories are **weak** `<35`, **moderate** `35–59.99`, **strong** `60–79.99`
and **very strong** `80–100`.

#### Breakouts and role reversal

Only closes count. A resistance break requires a close above the zone upper
bound plus `--sr-breakout-min-distance-pct`; a support break uses the
corresponding close below the lower bound. Intraday wicks do not increment the
counter, and a failed close resets it. Require consecutive confirming closes
with `--sr-breakout-confirmation-closes`. Add
`--sr-require-breakout-volume` to require every confirming bar to meet
`--sr-breakout-volume-multiplier` times its rolling 50-session average volume.

After the final confirming close, the first later bar that tests the old zone
and closes within it or on its new side marks resistance-turned-support or
support-turned-resistance; the close need not clear the zone's far edge.
Disable this with `--sr-no-role-reversal`. A retest filter refers to a retest
on the current scan bar; the persistent
`role_reversal_detected` field reports any detected reversal in the retained
history.

#### VCP interpretation and JSON output

The overlay adds the requested flat fields (`nearest_support_*`,
`nearest_resistance_*`, distances, strength, reward/risk, inside-zone and
break/breakdown flags) plus a complete nested `support_resistance` object. Its
explainable VCP signals are:

- `pivot_matches_resistance_zone` — the pivot falls in or within the fixed 1%
  margin around a resistance zone.
- `breakout_above_resistance` — price is above the close-confirmed broken
  resistance zone aligned with the VCP pivot.
- `retest_of_breakout_zone` — the current bar retests resistance now acting as
  support.
- `last_contraction_support` — active support nearest the final contraction
  low.
- `base_support_zone` — the highest-scoring active support zone.
- `distance_from_vcp_pivot_pct` — signed current-close distance from the VCP
  pivot.
- `pivot_resistance_distance_pct` — absolute distance from the pivot to the
  closest resistance-zone midpoint.
- `breakout_volume_confirmed` — the existing VCP volume calculator confirmed
  breakout expansion.
- `breakout_holds_above_zone` — current price remains above a close-confirmed
  broken resistance zone.

This repository has no chart frontend. JSON reports are chart-ready: zone
objects contain bounds, midpoint, role, touch/confirmation dates, strength and
role-reversal metadata, while `chart_markers` supplies the latest price, VCP
pivot and confirmed breakout point. An abridged result (generated from
deterministic daily bars) looks like:

```json
{
  "nearest_support": 96.45,
  "nearest_support_lower": 95.85,
  "nearest_support_upper": 97.05,
  "nearest_support_strength": "strong",
  "support_distance_pct": -4.47,
  "nearest_resistance": 106.75,
  "nearest_resistance_lower": 105.35,
  "nearest_resistance_upper": 108.15,
  "nearest_resistance_strength": "very_strong",
  "resistance_distance_pct": 5.73,
  "reward_risk_ratio": 1.28,
  "pivot_matches_resistance_zone": true,
  "pivot_resistance_distance_pct": 0.05,
  "breakout_above_resistance": false,
  "support_resistance": {
    "status": "ok",
    "zones": [
      {
        "type": "resistance",
        "lower": 105.35,
        "upper": 108.15,
        "midpoint": 106.75,
        "touches": 10,
        "strength_score": 88.11,
        "strength": "very_strong",
        "strength_components": {
          "touches": 30.0,
          "recency": 11.35,
          "reaction": 20.0,
          "volume": 6.76,
          "time_near_zone": 10.0,
          "major_swing": 10.0,
          "role_reversal": 0.0
        }
      }
    ],
    "chart_markers": {
      "latest_price": {"price": 100.96, "date": "2025-09-09"},
      "vcp_pivot": {"price": 108.0, "date": null},
      "breakout_point": null
    }
  }
}
```

#### Configuration and optional filters

The ratio-valued tolerance and breakout-distance options use decimal fractions
(`0.005` = 0.5%); filter distances use percentage points (`3` = 3%). These
options are shared by `screen_vcp.py` and `backtest_vcp.py`:

| CLI option | Default | Effect |
|---|---:|---|
| `--no-support-resistance` | off | Disable enrichment; default `enabled` is `true` |
| `--sr-swing-window` | `5` | Bars required on each side of a strict swing |
| `--sr-lookback-period` | `252` | Daily bars retained for zone analysis |
| `--sr-atr-period` | `14` | ATR averaging period |
| `--sr-zone-tolerance-pct` | `0.005` | Decimal price tolerance used for clustering |
| `--sr-zone-tolerance-atr` | `0.5` | ATR multiple used for clustering |
| `--sr-minimum-touches` | `2` | Minimum distinct touch dates |
| `--sr-breakout-confirmation-closes` | `1` | Required consecutive closes beyond a zone |
| `--sr-breakout-min-distance-pct` | `0.0` | Decimal minimum close distance beyond a zone |
| `--sr-breakout-volume-multiplier` | `1.2` | Required multiple of rolling 50-session volume when volume confirmation is enabled |
| `--sr-require-breakout-volume` | off | Enable breakout-volume confirmation |
| `--sr-no-role-reversal` | off | Disable role reversals; default `role_reversal_enabled` is `true` |
| `--sr-max-support-zones` | `3` | Maximum nearest active support zones returned |
| `--sr-max-resistance-zones` | `3` | Maximum nearest active resistance zones returned |
| `--sr-minimum-zone-strength` | `moderate` | Minimum returned strength: `weak`, `moderate`, `strong`, or `very_strong` |

The serialized config also records `pivot_zone_tolerance_pct: 0.01` (1%) for
VCP pivot matching. This value currently has no CLI override.

All filters are inactive by default and combine with AND when multiple flags
are supplied:

| Optional filter | Keeps candidates where… |
|---|---|
| `--sr-near-support-pct X` | Absolute distance to the support midpoint is at most `X` percentage points and support is strong by default; use `--sr-min-support-strength very_strong` to raise the requirement |
| `--sr-below-resistance-pct X` | Resistance midpoint is 0 to `X` percentage points above price |
| `--sr-breaking-above-resistance` | A strong-or-better resistance break is confirmed and price remains above that zone |
| `--sr-retesting-former-resistance` | The current bar retests confirmed former resistance as support |
| `--sr-min-support-strength LEVEL` | Nearest support is at least `weak`, `moderate`, `strong`, or `very_strong` |
| `--sr-min-resistance-strength LEVEL` | Nearest resistance is at least the selected category |
| `--sr-min-reward-risk-ratio RATIO` | Midpoint reward/risk is at least `RATIO` |
| `--sr-pivot-near-resistance-pct X` | VCP pivot is within `X` percentage points of the closest resistance-zone midpoint |
| `--sr-vcp-breakout-above-resistance` | The VCP candidate is above a confirmed broken resistance zone |

For example, require two closes at least 1% beyond a zone with 1.5× volume:

```bash
python3 scripts/screen_vcp.py --universe AAPL MSFT \
  --sr-breakout-confirmation-closes 2 \
  --sr-breakout-min-distance-pct 0.01 \
  --sr-require-breakout-volume --sr-breakout-volume-multiplier 1.5 \
  --output-dir reports/
```

Or screen within 3% of strong support with at least 1.5 midpoint reward/risk:

```bash
python3 scripts/screen_vcp.py --universe AAPL MSFT \
  --sr-near-support-pct 3 --sr-min-support-strength strong \
  --sr-min-reward-risk-ratio 1.5 --output-dir reports/
```

#### Limitations

- Detection uses daily OHLCV, not intraday or tick data. Besides relative daily
  volume around touches, it admits at most three ≥1.5×-volume daily closes as a
  coarse price proxy; this is not a tick-level volume profile or a true
  volume-profile node calculation.
- Yahoo mode and the backtest's `--csv-data` path use raw, unadjusted OHLC, so
  splits and other corporate actions can create artificial gaps or zones. The
  backtest's `--price-csv` path scales OHLC using `Adj Close`, but still depends
  on the source's adjustment quality.
- New listings, sparse histories and invalid/missing candles can produce
  `insufficient_data`, `no_zones` or `null` nearest-zone fields. A default swing
  alone needs 11 valid sessions; stable multi-touch zones usually need much
  more history.
- Zone discovery and scoring add work per evaluated symbol and historical
  cursor. Large-universe/backtest runs can be slower; use
  `--no-support-resistance` when the overlay is not needed, or reduce
  `--sr-lookback-period` after validating the trade-off.
- Strength and midpoint reward/risk are explainable heuristics, not calibrated
  reversal probabilities. Reward/risk ignores fills, slippage, gaps, costs and
  the probability of reaching either zone.

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
Close,Volume`, ISO dates). Build one for the current S&P 500 snapshot with:

```bash
# Downloads max available daily history per ticker (batched, atomic replace)
python3 scripts/download_sp500_history.py                 # → SP500_Historical_Data.csv
python3 scripts/download_sp500_history.py --start 2016-01-01 --output data/sp500.csv
```

Then point the pipeline at it:

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
| [`edge_pullback_interaction.py`](scripts/edge_pullback_interaction.py) | Do the two shipped overlays compound — does pullback Δ concentrate in high-Edge names? *(No — substitutes, not complements)* |
| [`grid_search.py`](scripts/grid_search.py) | Detection-parameter grid (108 combos; deflated Sharpe ≈ 0) |
| [`signal_family_experiment.py`](scripts/signal_family_experiment.py) | Any non-VCP signal in this tape? 12-1 momentum / RSI(2) mean-rev / 52w-high *(momentum only — until PIT)* |
| [`momentum_validation.py`](scripts/momentum_validation.py) | Momentum follow-ups: turnover+costs, PIT membership, lookbacks, vol scaling, R2K benchmark swap *(PIT cuts ~60% → +0.3%/mo, ns)* |
| [`industry_momentum_vcp_experiment.py`](scripts/industry_momentum_vcp_experiment.py) | Does a frozen 6-1 GICS industry-momentum gate rescue support-qualified VCPs? *(No — fewer trades, still negative OOS)* |
| [`fetch_r2k_membership.py`](scripts/fetch_r2k_membership.py) | Rebuild R2K PIT membership intervals from quarterly IWM holdings snapshots |
| [`build_trade_log_page.py`](scripts/build_trade_log_page.py) | Render trades JSONs into an interactive HTML ledger |

(The signal-family and momentum CLIs run straight off price data —
`--price-csv` or `--symbols-json` — rather than a trades JSON.)

## Refreshing index constituents

Membership snapshots live in `scripts/data/`. Refresh with:

```bash
python3 scripts/refresh_constituents.py --index both
```

## Tests

```bash
# Support/resistance unit and integration coverage
python3 -m pytest \
  tests/test_support_resistance_calculator.py \
  tests/test_support_resistance_integration.py -v

# Full suite
python3 -m pytest tests/ -v
```

## Docs

- `references/vcp_methodology.md` — VCP theory and the 7-point Trend Template
- `references/scoring_system.md` — composite scoring and rating bands
- `references/data_source.md` — yfinance data source and snapshot refresh

## Disclaimer

For research and education only. Nothing here is investment advice; past
pattern statistics do not predict future returns.
