# Trial 505–518 — Positive Relative-Strength Divergence Gate

Status: **frozen before signal counts, return evaluation, validation or
best-available OOS access** on 2026-08-02.

## Research question and prior overlap

Test whether an otherwise unchanged frozen VCP v1 buy signal improves when the
stock has a strictly positive 20-common-session adjusted-close return and that
return is strictly greater than SPY's return over the same common dates.

This is a per-stock confirmation gate, not aggregate S&P 500 breadth. It is
also narrower than Trial 340–344, which required a fresh 63-session stock/SPY
ratio high, changed entry timing and used a new joint RS/stock exit. The present
experiment changes only eligibility at the existing buy-signal close. The
economic family nevertheless overlaps prior relative-strength and momentum
research, so all declared comparisons count toward multiplicity.

## Frozen baseline and timing

Variant A is the unchanged v1 portfolio strategy in
`references/frozen_strategy_v1.md` and the default `pullback` path in
`scripts/portfolio_backtest.py`:

- default VCP detections;
- first confirmed pivot breakout, followed within 15 sessions by the first
  MA20 touch-and-hold close;
- that completed close is `signal_date`; fill remains the following session's
  open;
- unchanged Edge Rank sizing/priority, capital, ten-name capacity,
  sector/name/ADV limits, 10 bps per-side baseline cost, initial stop and
  60-session timeout;
- SPY is benchmark-only and never a holding.

The divergence state is evaluated at `signal_date`, after the existing entry
condition is already satisfied. It may remove that next-open order but may not
delay, advance, resize or rerank it.

## Price and calendar convention

`CSVClient` scales OHLC by `Adj Close / Close` and sets both `close` and
`adjClose` to adjusted close. The experiment prefers `adjClose` and falls back
to `close`, identically for stock and SPY.

For a requested date `t`, sort copies of both inputs without mutation, retain
only valid positive-price observations dated no later than `t`, intersect the
actual date sets, and use the latest common date plus the common date exactly
`L` observations earlier. Do not subtract independent array indexes, backfill
from a future observation or use the entry-day close. Weekend, holiday and
one-series missing dates therefore resolve only to an already completed common
session. Record the actual common end date as `divergence_signal_date`. Return
unavailable when fewer than `L + 1` valid common observations exist.

PIT membership must be true on the detection date, signal date and fill date.
The report counts membership and missing-history exclusions separately.

## Prespecified variants

- **A — baseline:** every unchanged eligible VCP order.
- **B — primary:** `stock_return_20d > 0` and
  `stock_return_20d - spy_return_20d > 0`.
- **C — negative control:** available 20-session observations that fail either
  strict primary condition. Missing observations belong to neither B nor C.
- **D — lookback sensitivity:** identical gate at 5, 10, 40 and 60 common
  sessions. These are multiple comparisons and cannot replace B.
- **E — threshold sensitivity:** at 20 sessions require positive stock return
  and divergence strictly above 0, 2 or 5 percentage points. Zero is B; 2 and
  5 are exploratory.
- **Descriptive buckets:** within each chronological partition, split available
  20-session divergence into fixed empirical quartiles. Report monotonicity;
  do not select a boundary from returns.
- **F — ranking:** not run. The engine uses `edge_rank` for both scarce-slot
  ordering and position sizing. Replacing it would change the fixed sizing
  model, while an approximate prefilter would not reproduce actual capacity.
  This omission cannot be interpreted in favour of the primary gate.

Attach to every evaluated order and matched trade:
`rs_divergence_lookback`, `stock_lookback_return_pct`,
`spy_lookback_return_pct`, `relative_divergence_pct`,
`positive_rs_divergence`, and `divergence_signal_date`.

## Multiplicity

Count fourteen new units: the 20-session lookback, own-return-positive
restriction, strict zero-divergence comparison, negative-control complement,
four lookback sensitivities, two positive threshold sensitivities, three extra
cost multipliers (2x/5x/10x) and quartile analysis. Declared multiplicity rises
from 504 to **518**. The omitted ranking experiment is not counted or tested.

## Chronology and sequential access

- Discovery/train: 2016-07-01 through 2018-06-30.
- Embargo: 2018-07-01 through 2018-12-31; never tune or score it.
- Validation: 2019-01-01 through 2021-12-31.
- Capped best-available OOS: 2022-01-01 through 2026-03-31. This period was
  opened by earlier research and is not genuinely untouched.

Before any P&L, the primary train gate must have at least 30 available
candidate orders. If it fails, close outcome-free. If it passes, evaluate all
prespecified train variants. Open validation only if the primary has at least
30 executed train trades, beats baseline train net CAGR, beats baseline
exposure-matched excess CAGR, has higher mean matched-window excess return than
the negative control, and retains positive expectancy after removing the best
five trades. Open best-available OOS only if the same directional comparisons
hold in validation, at least 30 validation trades execute, and primary MDD is
not more than two percentage points worse than baseline.

No sensitivity result may alter these gates or replace the primary.

## Evaluation and decision

For each opened partition/variant, save actual portfolio trades and daily
equity. Report portfolio CAGR, total return, annual volatility, Sharpe,
Sortino, Calmar, MDD, average exposure, utilization, turnover, estimated
costs, positions, rejections, exposure-matched excess performance and calendar
years. Report trade count/retention, gross and net mean/median/win rate/PF,
worst trade, matched SPY and excess statistics, standard error, t-stat and
bootstrap CI. Include pass-versus-fail lift, fixed divergence quartiles,
top/bottom-five trim, winsorization, score cohorts, SPY trend, volatility and
breadth regimes where their repository data are available.

The final classification is `IMPROVES` only if the primary opens and improves
best-available OOS excess return and portfolio performance with consistent,
cost-robust, non-outlier-dependent evidence and at least 30 useful OOS trades.
Mixed or sealed evidence is `INCONCLUSIVE`; consistently adverse OOS evidence
is `WORSENS`. Score A/B/C/D, normalized raw score, every applicable hard cap
and final capped score must be explicit.

No 2000–2005 data is required or permitted.
