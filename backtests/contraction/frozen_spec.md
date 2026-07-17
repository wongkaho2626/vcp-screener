# Frozen Spec — Contraction-Tightening Sequence Conditioning (declared 2026-07-17, before any results)

## Hypothesis

Minervini's textbook VCP requires *successively shrinking* contractions — each
pullback roughly half the depth of the prior one. The detection metadata
records every contraction's depth, so the claim is directly testable for the
first time: trades whose base shows a proper tightening sequence
(**tightening_ratio = last contraction depth ÷ first contraction depth ≤ 0.5**)
should earn higher per-trade excess vs SPY than loose sequences (> 0.5).

This is the follow-up explicitly flagged in the stop-width verification report:
measure the base itself from detection metadata, without touching exit
behavior. It is a detection-structure feature, not another cut of the trade
log's own fields, and it isolates a specific structural claim that the buried
composite-score gates never tested on its own.

## Frozen rule (no post-hoc changes)

- Samples: trades joined to their detections on (symbol, as_of_date).
  S&P (primary): `backtests/csv_full/vcp_trades_2026-07-10_004804.json` +
  `backtests/csv_full/vcp_backtest_2026-07-10_004737.json`.
  R2K (cross-universe): `backtests/r2k/vcp_trades_merged.json` +
  `backtests/r2k/vcp_backtest_2026-07-10_010704.json` and
  `backtests/r2k/vcp_backtest_2026-07-10_013013.json`.
- Feature: `tightening_ratio = contractions[-1].depth_pct /
  contractions[0].depth_pct` from `vcp_pattern.contractions` (chronological
  order as stored). Requires ≥ 2 contractions and a positive first depth;
  trades failing the join or the requirement are excluded and counted.
- Causal: contraction geometry is fully formed at `as_of_date`; nothing after
  the detection bar is consulted.
- Groups: **tight** = ratio ≤ 0.5 (proper halving); **loose** = ratio > 0.5.
- Metric: per-trade `excess_vs_spy_pct`. Raw returns context only.
- Test: Welch two-sample t on group means (tight − loose). Success = positive
  and |t| ≥ 1.65 with fold/trim/cross-universe consistency. A Spearman
  rank check of ratio vs excess is also reported (declared direction:
  negative correlation — lower ratio, higher excess).
- Costs: conditioning on an existing gross trade log; groups share the
  fill/cost model, so the difference is cost-invariant.

## Robustness bar (all declared now)

1. Fold split by entry_date: 2016–2020 vs 2021–2026 — same sign both folds.
2. Outlier trim: drop-top-5 and drop-top-10 by excess — no sign flip.
3. Cross-universe: replicate on R2K — same sign required.
4. Threshold sensitivity (robustness only, never adopted): splits at 0.4 and
   0.6.

## Give-up criteria (declared now)

- Primary (S&P) pooled |t| < 1.65 in the declared direction, or fold
  sign-flip, or trim sign-flip, or R2K sign-flip → null; record and bury.
- Structural caps: survivorship-biased universes cap any backtest-analyst
  score at 20; no true walk-forward caps at 55.
- Max 3 evaluation rounds; no threshold tuning to chase the score.

## Multiplicity

Approximately trial ~189 on this price history (after latency ~188). Frozen
cell plus two sensitivity cells adds 3 to the family.
