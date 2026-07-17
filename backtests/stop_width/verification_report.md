# Backtest Verification Report — Initial Stop-Width (Base Tightness) Conditioning

## Backtest Score: 7 / 100 — Reject

The declared hypothesis (tighter initial stops mark higher-quality bases) is not
supported: on the primary S&P sample the sign is *reversed* (tight −2.08% vs wide
−0.11% excess, Welch t −1.13, ns), and the R2K replication disagrees in sign with
S&P while flipping sign across its own folds.

| Component | Score | Max |
|---|---:|---:|
| A. Statistical Validity & Significance | 3 | 30 |
| B. Risk-Adjusted Performance | n/a (no equity curve — weight redistributed) | 25 |
| C. Robustness & Out-of-Sample | 2 | 25 |
| D. Trade Quality & Consistency | 0 | 20 |
| Raw total (measured basis 75, rescaled to 100) | 5/75 → **7** | 100 |
| Caps applied | Survivorship bias → 20; no true walk-forward → 55 | |
| **Final score** | **7** | **100** |

Component B is not scored: trade-log conditioning study with no daily equity
curve; weight redistributed per the missing-components rule.

## Executive Summary

Across 184 S&P and 918 R2K trades, the pipeline's own base-tightness measure
(initial risk width, entry-to-stop) does not predict per-trade excess vs SPY in
the declared direction. S&P tight-stop trades are *worse* (−1.97 pp, t −1.13,
P(diff>0) 12.7%), and the predeclared mechanical confound explains it: 64.5% of
tight trades exit on the stop versus 45.1% of wide trades — tight stops get
tagged out by noise before the trend can pay. R2K shows nothing (+0.27 pp,
t 0.21, fold signs opposed). A further structural finding: 52% (S&P) and 71%
(R2K) of trades sit at the simulator's 8% risk cap, so the observable width
variation is heavily truncated. Null recorded; give-up criteria fired round 1.

## 1. Performance Metrics (conditioning slices, excess vs SPY)

| Universe / slice | n tight | n wide | mean tight | mean wide | diff (pp) | Welch t | p |
|---|---:|---:|---:|---:|---:|---:|---:|
| **S&P pooled (frozen ≤6%)** | 31 | 153 | −2.08 | −0.11 | −1.97 | −1.13 | 0.265 |
| S&P fold 2016–2020 | 12 | 51 | −1.25 | +0.32 | −1.57 | −0.61 | 0.547 |
| S&P fold 2021–2026 | 19 | 102 | −2.60 | −0.33 | −2.27 | −0.96 | 0.347 |
| S&P drop-top-5 / -10 | — | — | — | — | −0.68 / −0.78 | −0.41 / −0.53 | 0.69 / 0.60 |
| **R2K pooled (frozen ≤6%)** | 81 | 837 | −0.21 | −0.47 | **+0.27** | +0.21 | 0.837 |
| R2K fold 2016–2020 | 43 | 323 | −1.51 | −0.34 | −1.17 | −0.63 | 0.535 |
| R2K fold 2021–2026 | 38 | 514 | +1.26 | −0.56 | +1.82 | +1.05 | 0.300 |

Group quality (excess basis): S&P tight PF 0.529 / win 32.3% vs wide PF 0.977 /
win 39.9%; R2K tight PF 0.946 vs wide 0.917 — noise. Sensitivity (robustness
only): S&P negative at 5% and 7% splits; R2K sign-incoherent (−1.49 at 5%,
+1.37 at 7%). No cell shows the declared effect.

Exit-reason mix (the predeclared confound): S&P tight 64.5% stop / 35.5%
timeout vs wide 45.1% / 54.9% — the mechanical stop-out channel dominates.

## 2. Statistical Significance

- Primary (S&P) declared-direction Welch t **−1.13** (p 0.27): wrong sign.
  Bootstrap (10,000 draws) 90% CI **[−4.72, +0.90]**, P(diff>0) = **12.7%**.
- R2K: t +0.21 (p 0.84), 90% CI [−1.86, +2.39], P(diff>0) = 58.2% — a coin flip.
- Cross-universe signs disagree (S&P −, R2K +): the declared robustness bar
  fails on the replication prong outright.
- Multiplicity: ~trial 187 on this history; frozen cell + 2 sensitivity cells.

## 3. Bias Assessment

| Bias | Status | Evidence |
|---|---|---|
| Lookahead | Absent | entry_price and stop_price are both fixed at entry; unit-tested annotation uses only those two fields |
| Survivorship | **Present** | Current-constituent universes; caps score at 20 |
| Data snooping | Partially mitigated | Direction, 6% threshold, metric, give-up criteria frozen before results; family multiplicity ~187 |
| Costs | Not applicable to the difference | Groups share the source log's fill/cost model |
| Range truncation | **Present, structural** | 52% (S&P) / 71% (R2K) of trades sit at the simulator's 8% risk cap — natural stop-width variation is censored, shrinking the tight group (n=31 S&P) |
| Confounded mechanism | **Present, predeclared** | Tight stops mechanically raise stop-out frequency (64.5% vs 45.1% on S&P); the test cannot separate base quality from stop mechanics |
| Regime overfit | Not applicable | No positive effect to overfit |

## 4. Robustness

- Fold split: S&P consistently negative (opposite the declared direction); R2K
  flips sign across folds (−1.17 → +1.82) — noise.
- Outlier trims: S&P stays negative (the *reversed* pattern is trim-stable, but
  it is post hoc); declared effect absent everywhere.
- Cross-universe: **failed** — pooled signs disagree between universes.
- Sensitivity: no coherent surface in either universe.
- No true re-optimising walk-forward (cap 55, moot under the 20 cap).

## 5. Red Flags 🚩

1. Declared direction is reversed on the primary sample and absent on R2K.
2. The mechanical confound dominates: tight stops = more stop-outs, exactly as
   predeclared in the frozen spec — the feature measures stop mechanics, not
   base quality.
3. The 8% risk cap censors most of the width distribution (52–71% of trades),
   leaving a small tight group (S&P n=31, borderline for inference).
4. Survivorship bias unresolved — caps any score at 20 regardless.

## 6. Improvement Recommendations 💡

1. Do not build any stop-width filter. Bury the hypothesis.
2. The Minervini tightness thesis, if ever retested, should be measured on the
   *base* itself (e.g. contraction depth sequence from detection metadata, not
   the risk-capped stop distance) with a mechanism that does not change exit
   behavior — otherwise the stop-out channel confound recurs.
3. If stop mechanics are studied instead, that is an *exit-rule* question, and
   the exit family is already buried (baseline stop + 60-bar timeout optimal).
4. Survivorship-safe data remains the only route above 20 for this pipeline.

## 7. Verdict

**7/100 — Reject.** The prespecified give-up criteria fired in round 1 (S&P
|t| < 1.65 with the wrong sign; cross-universe sign disagreement). The
predeclared confound (tight stops die early) is visible in the exit-reason mix
and explains the reversal. Under house rules — no threshold tuning, no post-hoc
direction swap — iteration cannot rescue this hypothesis, and the survivorship
cap binds regardless. Experiment closed as a null; recorded in CLAUDE.md
established results and the memory index.
