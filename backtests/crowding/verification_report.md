# Backtest Verification Report — VCP Signal-Crowding Conditioning

## Backtest Score: 7 / 100 — Reject

The declared effect (crowded detections earn lower excess vs SPY) is directionally
present but statistically absent on the primary sample (S&P Welch t −0.42, p 0.68)
and fails the trim and sensitivity prongs; the prespecified give-up criteria fired
on evaluation round 1.

| Component | Score | Max |
|---|---:|---:|
| A. Statistical Validity & Significance | 3 | 30 |
| B. Risk-Adjusted Performance | n/a (no equity curve — weight redistributed) | 25 |
| C. Robustness & Out-of-Sample | 2 | 25 |
| D. Trade Quality & Consistency | 0 | 20 |
| Raw total (measured basis 75, rescaled to 100) | 5/75 → **7** | 100 |
| Caps applied | Survivorship bias → 20; no true walk-forward → 55 | |
| **Final score** | **7** | **100** |

Component B is not scored: trade-log conditioning study with no daily equity curve
for a crowding-filtered book; weight redistributed per the missing-components rule.

## Executive Summary

Across 184 S&P and 918 R2K trades, detection crowding (≥2 co-detections in the
trailing 10 calendar days, on `as_of_date`, strictly causal) does not usefully
predict per-trade excess vs SPY. The S&P difference is small and insignificant
(−0.76 pp, t −0.42), flips sign under outlier trims, and flips sign across
sensitivity cells — a noise surface. R2K is consistently negative (−1.89 pp,
t −1.27, P(diff<0) 90.5%) but never significant, and its nominal t overstates
independence because 745 of 918 trades sit in overlapping clusters. Null recorded.

## 1. Performance Metrics (conditioning slices, excess vs SPY)

| Universe / slice | n crowded | n quiet | mean crowded | mean quiet | diff (pp) | Welch t | p |
|---|---:|---:|---:|---:|---:|---:|---:|
| **S&P pooled (frozen)** | 52 | 132 | −0.99 | −0.23 | −0.76 | −0.42 | 0.676 |
| S&P fold 2016–2020 | 17 | 46 | −0.52 | +0.22 | −0.74 | −0.23 | 0.824 |
| S&P fold 2021–2026 | 35 | 86 | −1.21 | −0.47 | −0.75 | −0.34 | 0.735 |
| S&P drop-top-5 | 51 | 128 | −1.64 | −1.47 | −0.18 | −0.11 | 0.911 |
| S&P drop-top-10 | 50 | 124 | −2.08 | −2.23 | **+0.15** | +0.10 | 0.921 |
| **R2K pooled (frozen)** | 745 | 173 | −0.81 | +1.08 | −1.89 | −1.27 | 0.206 |
| R2K fold 2016–2020 | 292 | 74 | −1.01 | +1.60 | −2.61 | −1.20 | 0.232 |
| R2K fold 2021–2026 | 453 | 99 | −0.68 | +0.69 | −1.37 | −0.67 | 0.503 |
| R2K drop-top-5 / -10 | — | — | — | — | −1.37 / −1.36 | −1.03 / −1.06 | 0.30 / 0.29 |

Group quality: S&P crowded PF 0.80 vs quiet 0.95; R2K crowded PF 0.85 vs quiet
1.18. Both groups in both universes have ≈0 or negative expectancy — consistent
with the programme-wide "entry alpha: none" result.

Sensitivity cells (robustness only, never adopted): S&P flips sign at
min_prior=1 (+2.34 pp), min_prior=3 (+0.60), window=5d (+1.93), window=15d
(+0.20) — the S&P surface is noise. R2K stays negative in all five cells
(min_prior=3 nominally t −2.05, p 0.04, before any multiplicity or
cluster-correlation correction).

## 2. Statistical Significance

- Primary (S&P) declared-direction Welch t **−0.42** (p 0.68): right sign, no
  signal. Bootstrap (10,000 draws) 90% CI on the difference **[−3.70, +2.24]**,
  P(diff<0) = 66.1% — the PSR analogue is far below the 90% bar.
- R2K: t −1.27 (p 0.21), bootstrap 90% CI [−4.44, +0.50], P(diff<0) = 90.5% —
  suggestive but insignificant, and materially overstated: 81% of R2K trades are
  "crowded", so cluster-overlapping holding windows shrink the effective sample
  well below the nominal 918 (caveat declared in the frozen spec).
- Multiplicity: ~trial 186 on this history; frozen cell + 4 sensitivity cells.
  Any DSR-style correction moves an already-null result further from significance.

## 3. Bias Assessment

| Bias | Status | Evidence |
|---|---|---|
| Lookahead | Absent | Feature counts only trailing `as_of_date` detections (inclusive window ends at own as_of); unit test enforces no-future counting |
| Survivorship | **Present** | Both universes are current-constituent sets (R2K lost ~26% of names); caps score at 20 |
| Data snooping | Partially mitigated | Direction, window, threshold, metric, give-up criteria frozen before results; family multiplicity still ~186 |
| Costs | Not applicable to the difference | Groups share the source log's fill/cost model |
| Cluster correlation | **Present, declared** | Crowded trades hold overlapping dates; nominal t overstates independence, especially on R2K (745/918 crowded) |
| Frequency mismatch | Absent | Daily as-of dates throughout |
| Regime overfit | Not applicable | No positive effect to overfit |

## 4. Robustness

- Fold split: S&P sign is stable (−0.74 / −0.75) but magnitudes are noise-level;
  R2K sign stable. The declared effect never reaches significance in any fold.
- Outlier trims: **S&P flips sign at drop-top-10 (+0.15)** — the declared
  give-up criterion (trim sign-flip) fired.
- Sensitivity: S&P flips sign in four of five cells — no coherent surface. R2K
  is coherent (all negative) but insignificant at the frozen cell.
- Cross-universe: the prong RAN this time (trade-log-only feature). Directional
  agreement (both negative) but the primary sample shows nothing, so replication
  of a null is just a null.
- No true re-optimising walk-forward (cap 55, moot under the 20 cap).

## 5. Red Flags 🚩

1. Primary-sample t is −0.42 — indistinguishable from zero; trim flips sign.
2. S&P sensitivity surface is sign-unstable across all four variation cells.
3. R2K's suggestive t −1.27 rests on 81% cluster-overlapped trades — effective
   sample far smaller than nominal; the one nominally significant cell
   (min_prior=3, p 0.04) is a robustness cell, not the frozen rule, and dies
   under multiplicity.
4. Survivorship bias unresolved — caps any score at 20 regardless.

## 6. Improvement Recommendations 💡

1. Do not build any crowding gate. Bury the hypothesis.
2. If crowding is ever revisited, it needs (a) detection-level (not
   executed-trade-level) counts from the full backtest JSON, (b) a
   cluster-robust inference method (block bootstrap by cluster), and (c) a
   fresh predeclared spec on new data. The R2K min_prior=3 cell may inform that
   prospective spec but must not be promoted from this sample.
3. Survivorship-safe data remains the only route above 20 for this pipeline.

## 7. Verdict

**7/100 — Reject.** The prespecified give-up criteria fired in round 1 (S&P
pooled |t| < 1.65 and trim sign-flip). Under house rules — no threshold tuning,
no post-hoc promotion of the R2K min_prior=3 cell — iteration cannot rescue the
hypothesis, and the survivorship cap binds regardless. Experiment closed as a
null; recorded in CLAUDE.md established results and the memory index.
