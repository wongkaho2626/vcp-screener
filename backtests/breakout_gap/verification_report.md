# Backtest Verification Report — Breakout-Day Opening Gap Conditioning

## Backtest Score: 7 / 100 — Reject

The declared hypothesis (gap-up entries earn higher excess vs SPY) is not supported:
the effect has the **opposite sign** (gap trades −2.97% vs no-gap +0.10% excess,
Welch t −1.43, p 0.16) and fails every prong of the declared success criteria.

| Component | Score | Max |
|---|---:|---:|
| A. Statistical Validity & Significance | 3 | 30 |
| B. Risk-Adjusted Performance | n/a (no equity curve — weight redistributed) | 25 |
| C. Robustness & Out-of-Sample | 2 | 25 |
| D. Trade Quality & Consistency | 0 | 20 |
| Raw total (measured basis 75, rescaled to 100) | 5/75 → **7** | 100 |
| Caps applied | Survivorship bias → 20; no true walk-forward → 55 | |
| **Final score** | **7** | **100** |

Component B is not scored: this is a trade-log conditioning study with no daily
equity curve for the gap-only book; its weight is redistributed per the missing-
components rule rather than treated as zero.

## Executive Summary

On 173 classified S&P VCP trades (2016–2026), entry-day opening gaps ≥ +1.0% do
not predict higher per-trade excess vs SPY — they predict *lower*. The declared
effect fails the prespecified give-up criteria (pooled |t| < 1.65 in the declared
direction), so under the house rules this experiment is a null and is buried
without parameter iteration. The opposite-sign pattern (gaps harmful) is fold-
consistent but post hoc, and is recorded as hypothesis-generating only.

## 1. Performance Metrics (conditioning slices, excess vs SPY)

| Slice | n gap | n no-gap | mean gap | mean no-gap | diff (pp) | Welch t | p |
|---|---:|---:|---:|---:|---:|---:|---:|
| Pooled (frozen 1.0%) | 30 | 143 | −2.97 | +0.10 | −3.07 | −1.43 | 0.158 |
| Fold 2016–2020 | 12 | 46 | −3.66 | +1.02 | −4.68 | −1.83 | 0.076 |
| Fold 2021–2026 | 18 | 97 | −2.51 | −0.33 | −2.18 | −0.68 | 0.503 |
| Drop-top-5 | 30 | 138 | −2.97 | −1.27 | −1.70 | −0.82 | 0.415 |
| Drop-top-10 | 27 | 136 | −5.70 | −1.60 | −4.11 | −2.79 | 0.008 |
| 0.5% threshold (robustness only) | 67 | 106 | −1.04 | −0.04 | −1.00 | −0.58 | 0.562 |
| 2.0% threshold (robustness only) | 5 | 168 | −3.84 | −0.33 | −3.51 | −1.65 | 0.150 |

Group trade quality (excess basis): gap PF 0.489, win rate 26.7%, avg win +10.63 /
avg loss −7.91; no-gap PF 1.024, win rate 40.6%. Raw-return basis shows the same
ordering (gap PF 0.81 vs no-gap 1.62) and is context only.

## 2. Statistical Significance

- Declared-direction Welch t: **−1.43** (df 45.3, p 0.158) — wrong sign; the
  prespecified success bar (t ≥ +1.65) is decisively missed.
- 10,000-draw IID bootstrap of the group-mean difference: 90% CI **[−6.39, +0.51]**,
  P(diff > 0) = **7.5%** — the PSR analogue for the declared effect.
- One-sample t of the gap group's own mean excess: −1.56 (a *negative* tilt).
- Multiplicity: this is approximately trial ~182 on this price history; the frozen
  1.0% threshold plus two sensitivity cells adds 3 cells to the family. Any DSR-style
  correction only pushes the (already null) declared effect further from significance.
- Sample adequacy: 173 pooled trades over 10.4 years is adequate; the gap group
  (n=30) is at the minimum for inference — borderline.

## 3. Bias Assessment

| Bias | Status | Evidence |
|---|---|---|
| Lookahead | Absent | Feature = entry-day open vs prior close; the open prints before any same-day fill (close or intraday pivot). Unit test enforces truncation-invariance |
| Survivorship | **Present** | Current-constituent CSV universe; caps score at 20 |
| Data snooping | Partially mitigated | Direction, threshold, metric and give-up criteria frozen in `frozen_spec.md` before results; family multiplicity still ~182 trials |
| Costs | Not applicable to the difference | Both groups share the source log's fill/cost model; group difference is cost-invariant |
| Fill alignment | Cannot fully verify | 43/173 entry prices differ >1% from the entry-day close, implying some intrabar pivot fills in the source simulator; does not affect the open-based feature's causality |
| Frequency mismatch | Absent | Daily bars throughout |
| Regime overfit | Not applicable | No positive effect exists to overfit |

## 4. Robustness

- Fold split: the declared positive effect appears in **neither** fold (both
  negative). For the post-hoc negative reading, the sign is consistent across folds
  but significance is absent in 2021–2026.
- Outlier trims: declared effect absent in both trims; drop-top-10 makes the
  *negative* difference nominally significant (t −2.79) — post hoc, not claimed.
- Threshold sensitivity (0.5% / 2.0%): negative at every threshold; no cell shows
  the declared effect. Smooth, coherent surface — the null is stable.
- Cross-universe (R2K): **not run** — no offline R2K OHLCV; recorded limitation.
- No true re-optimising walk-forward exists (cap 55, moot under the 20 cap).

## 5. Red Flags 🚩

1. Effect sign is opposite to the declared hypothesis in every slice examined.
2. Gap group expectancy is negative on both excess and raw bases (PF 0.489 excess).
3. Survivorship-biased universe — unresolvable with current data; caps at 20.
4. Gap group n=30 is minimal; fold subgroups (12/18) are thin for inference.
5. 43/173 fills deviate >1% from entry-day close — source-log fill convention is
   mixed and worth a one-time audit in `trade_simulator.py`.

## 6. Improvement Recommendations 💡

1. Do not add any gap-based entry filter. Bury the hypothesis per house rules.
2. The opposite-direction observation ("gap-up entries are adversely selected —
   chasing urgency buys extended opens") rhymes with prior lessons (fib-fill
   adverse selection, pullback > breakout). If ever revisited, it must be a fresh
   predeclared hypothesis on new data — e.g. *avoiding* entries on ≥1% gap days —
   not a re-read of this sample.
3. Audit the source trade log's fill convention (close vs pivot) once, for
   documentation; it does not change this verdict.
4. A survivorship-safe security master with delisted names remains the only route
   to scores above 20 for any experiment on this pipeline.

## 7. Verdict

**7/100 — Reject.** The prespecified give-up criteria fired on the first
evaluation round (declared-direction t < 1.65, wrong sign throughout). Under the
house rules — no parameter tuning to chase a score, no post-hoc direction swap —
iteration cannot rescue this hypothesis, and the structural survivorship cap (20)
binds regardless. Experiment closed as a null; recorded in CLAUDE.md established
results and the memory index.
