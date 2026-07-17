# Backtest Verification Report — Base-Duration (Maturity) Conditioning

## Backtest Score: 6 / 100 — Reject

The declared effect (five-week-plus bases better) is absent: S&P pooled Welch t
−0.11 (wrong sign), folds flip sign within both universes, trims flip against
the pooled sign, sensitivity cells flip randomly, and Spearman ≈ 0 everywhere.

| Component | Score | Max |
|---|---:|---:|
| A. Statistical Validity & Significance | 3 | 30 |
| B. Risk-Adjusted Performance | n/a (no equity curve — weight redistributed) | 25 |
| C. Robustness & Out-of-Sample | 1 | 25 |
| D. Trade Quality & Consistency | 0 | 20 |
| Raw total (measured basis 75, rescaled to 100) | 4/75 → **6** | 100 |
| Caps applied | Survivorship bias → 20; no true walk-forward → 55 | |
| **Final score** | **6** | **100** |

Component B is not scored: trade-log conditioning study with no daily equity
curve; weight redistributed per the missing-components rule.

## Executive Summary

Minervini's five-week base-maturity claim, tested directly from detection
metadata (`pattern_duration_days`, 100% join rate on both universes), carries
no information about subsequent excess vs SPY. The S&P pooled difference is
−0.19 pp against the declared direction (t −0.11, bootstrap P(diff>0) = 46.3%
— a coin flip), every robustness slice flips sign somewhere, and the duration
gradient is flat (Spearman +0.08 / +0.02, both ns). Give-up criteria fired on
round 1. Per the frozen spec's own declaration, this closes the
detection-metadata single-attribute conditioning family alongside the
trade-log family.

## 1. Performance Metrics (conditioning slices, excess vs SPY)

| Universe / slice | n mature | n short | mean mature | mean short | diff (pp) | Welch t | p |
|---|---:|---:|---:|---:|---:|---:|---:|
| **S&P pooled (frozen ≥35d)** | 59 | 125 | −0.57 | −0.38 | −0.19 | −0.11 | 0.912 |
| S&P fold 2016–2020 | 22 | 41 | +0.28 | −0.11 | **+0.39** | +0.15 | 0.883 |
| S&P fold 2021–2026 | 37 | 84 | −1.08 | −0.51 | **−0.57** | −0.25 | 0.805 |
| S&P drop-top-5 / -10 | — | — | — | — | **+1.41** / +0.68 | +0.89 / +0.46 | 0.38 / 0.65 |
| **R2K pooled (frozen ≥35d)** | 265 | 653 | −0.40 | −0.47 | **+0.07** | +0.06 | 0.949 |
| R2K folds | — | — | — | — | +0.43 / −0.19 | +0.29 / −0.12 | 0.77 / 0.90 |
| R2K trims | — | — | — | — | +0.30 / +0.43 | +0.30 / +0.45 | 0.77 / 0.65 |

Median duration: 31 days (S&P) / 28 days (R2K). Sensitivity cells (robustness
only) flip sign freely — S&P: +2.23 at 25d vs −3.78 at 50d; R2K: −0.95 at 25d
vs +0.98 at 50d. Spearman(duration, excess): S&P +0.077 (p 0.30), R2K +0.019
(p 0.56) — no gradient.

## 2. Statistical Significance

- Primary (S&P) declared-direction Welch t **−0.11** (p 0.91, wrong sign).
  Bootstrap (10,000 draws) 90% CI **[−2.99, +2.59]**, P(diff>0) = **46.3%**.
- R2K: t +0.06 (p 0.95) — pooled signs disagree between universes.
- Multiplicity: ~trial 190 on this history; moot for t-values this small.
- Sample adequacy: 100% join; groups 59/125 and 265/653 — adequate for
  detecting any real effect of usable size; none exists.

## 3. Bias Assessment

| Bias | Status | Evidence |
|---|---|---|
| Lookahead | Absent | `pattern_duration_days` is complete at `as_of_date`; join on (symbol, as_of_date); unit-tested skip rules |
| Survivorship | **Present** | Current-constituent universes; caps score at 20 |
| Data snooping | Partially mitigated | Direction, 35-day threshold (canonical five weeks), metric, give-up criteria frozen before results; feasibility peek examined the duration distribution only, never outcomes |
| Costs | Not applicable to the difference | Groups share the source log's fill/cost model |
| Detector truncation | Present, declared | The detector's own minimum window (observed min 15 days) truncates the short tail; "short" here means 15–34 days, not arbitrary shelves |
| Regime overfit | Not applicable | No effect to overfit |

## 4. Robustness

- Fold split: sign flips inside both universes — fired the give-up criterion.
- Outlier trims: flip the pooled S&P sign (+1.41 after drop-top-5) — noise.
- Cross-universe: pooled signs disagree (S&P −, R2K +).
- Sensitivity: no coherent surface in either universe; the 50d cell's nominal
  t −1.80 sits on n=15 and is the opposite sign of the 25d cell.
- No true re-optimising walk-forward (cap 55, moot under the 20 cap).

## 5. Red Flags 🚩

1. Every robustness axis (folds, trims, universes, thresholds) produces sign
   flips — textbook noise behaviour.
2. The detector already enforces a minimum pattern window, so the claim's
   sharpest version (rejecting sub-3-week shelves) is untestable here;
   recorded as a scope limit, not evidence for the claim.
3. Survivorship bias unresolved — caps any score at 20 regardless.

## 6. Improvement Recommendations 💡

1. Do not gate on base duration. Bury the hypothesis.
2. Per the frozen spec: the detection-metadata single-attribute family is now
   **closed** (contraction depth — reversed; base duration — null), joining
   the exhausted trade-log family. Six conditioning experiments on this
   history have produced zero usable gates. Any further work on this data is
   expected to re-measure noise; the programme's next legitimate move remains
   a survivorship-safe security master with delisted names and PIT membership.
3. If the Minervini structural claims are ever retested, do it detection-level
   on new data with multivariate controls — the two textbook attributes tested
   so far were, if anything, adversely selected.

## 7. Verdict

**6/100 — Reject.** The prespecified give-up criteria fired in round 1 (wrong
pooled sign, fold and trim sign-flips, cross-universe disagreement, flat
gradient). The survivorship cap binds regardless. Experiment closed as a null;
the detection-metadata conditioning family is closed with it, per the frozen
spec's declaration. Recorded in CLAUDE.md established results and the memory
index.
