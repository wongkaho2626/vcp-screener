# Frozen Spec — Detection-to-Entry Latency Conditioning (declared 2026-07-17, before any results)

## Hypothesis

The pipeline detects a VCP near its pivot (`as_of_date`) and enters only when
the breakout actually triggers (`entry_date`). The wait between the two is the
market's own reveal of demand: strong-demand names punch through the pivot
within days, while weak names loiter beneath it. Declared direction: **fresh
breakouts (entry ≤ 7 calendar days after detection) earn higher per-trade
excess vs SPY than stale ones (> 7 days)**.

## Frozen rule (no post-hoc changes)

- Samples: `backtests/csv_full/vcp_trades_2026-07-10_004804.json` (S&P, 184
  trades, primary) and `backtests/r2k/vcp_trades_merged.json` (R2K, 918
  trades, cross-universe prong). Trade-log fields only; no price bars needed.
- Feature: `latency_days = entry_date − as_of_date` in calendar days. Causal:
  both dates are known at the moment of entry; the rule consults nothing after
  the fill.
- Groups: **fresh** = latency_days ≤ 7; **stale** = latency_days > 7. (7 = one
  calendar week, declared a priori, not fitted; trades with negative latency,
  if any, are dropped and counted as data errors.)
- Metric: per-trade `excess_vs_spy_pct`. Raw returns context only.
- Test: Welch two-sample t on group means (fresh − stale). Success = positive
  and |t| ≥ 1.65 with fold/trim/cross-universe consistency.
- Confound declared upfront: the 60-bar timeout clock starts at entry for both
  groups, so holding periods are comparable; but stale entries occur later in
  the base's life, mildly entangling latency with base duration. No correction
  is attempted; stated as a limitation.
- Costs: conditioning on an existing gross trade log; groups share the
  fill/cost model, so the difference is cost-invariant.

## Robustness bar (all declared now)

1. Fold split by entry_date: 2016–2020 vs 2021–2026 — same sign both folds.
2. Outlier trim: drop-top-5 and drop-top-10 by excess — no sign flip.
3. Cross-universe: replicate on R2K — same sign required.
4. Threshold sensitivity (robustness only, never adopted): splits at 4 and 14
   calendar days.

## Give-up criteria (declared now)

- Primary (S&P) pooled |t| < 1.65 in the declared direction, or fold
  sign-flip, or trim sign-flip, or R2K sign-flip → null; record and bury.
- Structural caps: survivorship-biased universes cap any backtest-analyst
  score at 20; no true walk-forward caps at 55.
- Max 3 evaluation rounds; no threshold tuning to chase the score.

## Multiplicity

Approximately trial ~188 on this price history (after stop-width ~187).
Frozen cell plus two sensitivity cells adds 3 to the family.
