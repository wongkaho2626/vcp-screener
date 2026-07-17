# Frozen Spec — Initial Stop-Width (Base Tightness) Conditioning (declared 2026-07-17, before any results)

## Hypothesis

Minervini's core claim is that tighter VCP bases are higher-quality setups. The
initial stop distance is the pipeline's own measure of base looseness: the stop
sits at the base low, so `risk_pct = (entry_price − stop_price) / entry_price`
is small exactly when the base is tight. Declared direction: **tight-stop trades
(risk_pct ≤ 6%) earn higher per-trade excess vs SPY than wide-stop trades**.

## Frozen rule (no post-hoc changes)

- Samples: `backtests/csv_full/vcp_trades_2026-07-10_004804.json` (S&P, 184
  trades, primary) and `backtests/r2k/vcp_trades_merged.json` (R2K, 918 trades,
  cross-universe prong). Trade-log fields only; no price bars needed.
- Feature: `risk_pct = (entry_price − stop_price) / entry_price × 100`,
  computed per trade. Causal: both prices are set at entry; no forward data.
- Groups: **tight** = risk_pct ≤ 6.0; **wide** = risk_pct > 6.0. (The simulator
  caps risk at 8%, so the observable range is roughly 2–8%; 6% is declared as
  the midpoint split, not fitted.)
- Metric: per-trade `excess_vs_spy_pct`. Raw returns context only.
- Test: Welch two-sample t on group means (tight − wide). Success = positive
  and |t| ≥ 1.65 with fold/trim/cross-universe consistency.
- Confound declared upfront: risk width also mechanically scales the
  stop-out probability (wide stops survive noise longer, tight stops get
  tagged out more) — so a null or negative result may reflect stop mechanics
  rather than base quality. Interpretation must separate "tightness predicts
  quality" from "tight stops die early"; the exit_reason mix per group will be
  reported for exactly this purpose.
- Costs: conditioning on an existing gross trade log; groups share the
  fill/cost model, so the difference is cost-invariant.

## Robustness bar (all declared now)

1. Fold split by entry_date: 2016–2020 vs 2021–2026 — same sign both folds.
2. Outlier trim: drop-top-5 and drop-top-10 by excess — no sign flip.
3. Cross-universe: replicate on R2K — same sign required.
4. Threshold sensitivity (robustness only, never adopted): splits at 5.0% and
   7.0%.

## Give-up criteria (declared now)

- Primary (S&P) pooled |t| < 1.65 in the declared direction, or fold sign-flip,
  or trim sign-flip, or R2K sign-flip → null; record and bury.
- Structural caps: survivorship-biased universes cap any backtest-analyst score
  at 20; no true walk-forward caps at 55.
- Max 3 evaluation rounds; no threshold tuning to chase the score.

## Multiplicity

Approximately trial ~187 on this price history (after breakout-gap ~182 and
crowding ~186). Frozen cell plus two sensitivity cells adds 3 to the family.
