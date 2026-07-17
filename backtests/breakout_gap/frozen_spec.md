# Frozen Spec — Breakout-Day Opening Gap Conditioning (declared 2026-07-17, before any results)

## Hypothesis

VCP breakout trades whose **entry day opens with a gap up ≥ +1.0%** versus the prior
session's close (a sign of institutional demand urgency) earn higher per-trade
excess vs SPY than trades without such a gap.

## Frozen rule (no post-hoc changes)

- Sample: executed trades in `backtests/csv_full/vcp_trades_2026-07-10_004804.json`
  (canonical CSV-data S&P run, 184 trades, close-based fills, stop + 60-bar timeout).
- Feature: `gap_pct = open(entry_date) / close(prior trading day) − 1`, computed
  from `SP500_Historical_Data.csv`. Causal: the open is known before the same-day
  close fill; no forward data consulted.
- Groups: **gap** = gap_pct ≥ +1.0%; **no-gap** = gap_pct < +1.0%.
- Metric: per-trade `excess_vs_spy_pct` (already exposure/date-matched per trade).
  Raw returns reported as context only.
- Test: Welch two-sample t on group means (gap − no-gap). Success direction: gap
  group higher.
- Costs: conditioning analysis on a gross trade log; both groups share the fill and
  cost model, so the group *difference* is cost-invariant. Stated, not stressed.

## Robustness bar (all declared now)

1. Fold split by entry_date: 2016-01-01–2020-12-31 vs 2021-01-01–2026-12-31 —
   effect must keep sign in both folds.
2. Outlier trim: drop top-5 and top-10 trades by excess from the pooled sample and
   recompute the group difference — must not flip sign.
3. Cross-universe: R2K OHLCV is not available offline (no local R2K price CSV), so
   this prong **cannot be run**; recorded as a limitation, not skipped silently.
4. Threshold sensitivity (robustness check only, never adopted): 0.5% and 2.0%.

## Give-up criteria (declared now)

- Pooled Welch |t| < 1.65, or fold sign-flip, or trim sign-flip → null; record and
  bury per house rules.
- Known structural caps on this data: survivorship-biased universe caps any
  backtest-analyst score at 20; ~180+ prior trials on this history apply to DSR.
- Max 3 backtest-analyst evaluation rounds; parameter tuning to chase the score is
  prohibited.

## Multiplicity

This is approximately trial ~182+ on this price history (counting prior experiment
families and grid cells). The 1.0% threshold plus two sensitivity cells adds 3
cells to the family.
