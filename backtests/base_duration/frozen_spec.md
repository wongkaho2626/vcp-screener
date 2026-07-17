# Frozen Spec — Base-Duration (Maturity) Conditioning (declared 2026-07-17, before any results)

## Hypothesis

Minervini's last untested structural claim in this pipeline: a proper VCP base
needs **at least five weeks** to form; shorter "shelf" patterns are lower
quality. The detection metadata records `pattern_duration_days`, so the claim
is directly testable. Declared direction: **mature bases
(pattern_duration_days ≥ 35) earn higher per-trade excess vs SPY than short
ones (< 35)**.

This is the time-dimension sibling of the contraction-depth test (which came
back reversed). It is the final major single-attribute structural claim
available in the detection metadata; if it nulls, the detection-metadata
conditioning family closes alongside the trade-log family.

## Frozen rule (no post-hoc changes)

- Samples: trades joined to detections on (symbol, as_of_date) — same
  machinery as the contraction experiment.
  S&P (primary): `backtests/csv_full/vcp_trades_2026-07-10_004804.json` +
  `backtests/csv_full/vcp_backtest_2026-07-10_004737.json`.
  R2K (cross-universe): `backtests/r2k/vcp_trades_merged.json` +
  `backtests/r2k/vcp_backtest_2026-07-10_010704.json` and
  `backtests/r2k/vcp_backtest_2026-07-10_013013.json`.
- Feature: `vcp_pattern.pattern_duration_days` (calendar days of pattern
  formation, complete at `as_of_date` — causal). Missing/non-positive values
  are excluded and counted. Feasibility (duration distribution only, no
  outcomes consulted): S&P median 31 days, 38.9% ≥ 35 — both groups
  well-populated.
- Groups: **mature** = duration ≥ 35 (Minervini's five-week minimum);
  **short** = duration < 35.
- Metric: per-trade `excess_vs_spy_pct`. Raw returns context only.
- Test: Welch two-sample t on group means (mature − short). Success = positive
  and |t| ≥ 1.65 with fold/trim/cross-universe consistency. Spearman
  (duration vs excess) also reported; declared direction positive.
- Costs: conditioning on an existing gross trade log; groups share the
  fill/cost model, so the difference is cost-invariant.

## Robustness bar (all declared now)

1. Fold split by entry_date: 2016–2020 vs 2021–2026 — same sign both folds.
2. Outlier trim: drop-top-5 and drop-top-10 by excess — no sign flip.
3. Cross-universe: replicate on R2K — same sign required.
4. Threshold sensitivity (robustness only, never adopted): splits at 25 and
   50 days.

## Give-up criteria (declared now)

- Primary (S&P) pooled |t| < 1.65 in the declared direction, or fold
  sign-flip, or trim sign-flip, or R2K sign-flip → null; record and bury,
  and close the detection-metadata conditioning family in the graveyard.
- Structural caps: survivorship-biased universes cap any backtest-analyst
  score at 20; no true walk-forward caps at 55.
- Max 3 evaluation rounds; no threshold tuning to chase the score.

## Multiplicity

Approximately trial ~190 on this price history (after contraction ~189).
Frozen cell plus two sensitivity cells adds 3 to the family.
