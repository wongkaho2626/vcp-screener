# Frozen Spec — VCP Signal-Crowding Conditioning (declared 2026-07-17, before any results)

## Hypothesis

When many VCP signals fire close together, the tape is frothy and breakouts are
crowded/chased; trades detected in such clusters earn **lower** per-trade excess
vs SPY than trades detected in quiet periods. (Direction declared: crowded worse.)

## Frozen rule (no post-hoc changes)

- Samples: executed trades in
  `backtests/csv_full/vcp_trades_2026-07-10_004804.json` (S&P, 184 trades) and
  `backtests/r2k/vcp_trades_merged.json` (R2K, 918 trades) — analysed
  separately; S&P is the primary sample, R2K is the cross-universe prong.
- Feature: for each trade, `n_prior` = number of *other* trades in the same
  universe whose `as_of_date` falls in the trailing **10-calendar-day** window
  ending at this trade's `as_of_date` (inclusive). Strictly causal: `as_of_date`
  is the detection date; all counted detections are known at or before it.
- Groups: **crowded** = `n_prior ≥ 2`; **quiet** = `n_prior < 2`.
- Metric: per-trade `excess_vs_spy_pct`. Raw returns context only.
- Test: Welch two-sample t on group means (crowded − quiet). Success = negative
  and |t| ≥ 1.65 with fold/trim consistency.
- Caveat declared upfront: clustered trades have overlapping holding windows, so
  outcomes within a cluster are correlated — the effective sample is smaller
  than the trade count; treat borderline t-values as weaker than nominal.
- Costs: conditioning on an existing gross trade log; groups share the fill/cost
  model, so the difference is cost-invariant.

## Robustness bar (all declared now)

1. Fold split by entry_date: 2016–2020 vs 2021–2026 — same sign both folds.
2. Outlier trim: drop-top-5 and drop-top-10 by excess — no sign flip.
3. Cross-universe: replicate on R2K (trade-log fields only, so this prong RUNS
   this time) — same sign required.
4. Threshold sensitivity (robustness only, never adopted): `n_prior ≥ 1` and
   `≥ 3`; window 5 and 15 days.

## Give-up criteria (declared now)

- Pooled S&P |t| < 1.65 in the declared direction, or fold sign-flip, or trim
  sign-flip, or R2K sign-flip → null; record and bury.
- Structural caps: survivorship-biased universes cap any score at 20; ~185
  prior trials on this history apply to any multiplicity correction.
- Max 3 backtest-analyst evaluation rounds; no parameter tuning to chase score.

## Relationship to buried work (stated honestly)

Market-breadth and regime gates are dead (external market-state variables, all
null). This tests a *strategy-internal* variable — the density of the VCP
signal stream itself — which no prior experiment touched. The breadth null
lowers the prior; the breakout-gap lesson (urgency/chasing = adverse selection)
raises it slightly. Trial count after this: ~186.
