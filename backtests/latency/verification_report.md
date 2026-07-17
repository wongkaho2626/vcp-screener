# Backtest Verification Report — Detection-to-Entry Latency Conditioning

## Backtest Score: 6 / 100 — Reject

The declared effect (fresh breakouts better) is statistically absent everywhere:
S&P pooled Welch t 0.12, fold and trim signs flip, and the continuous check
(Spearman latency-vs-excess −0.04 S&P / +0.01 R2K) shows no relationship at all.

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

Across 184 S&P and 918 R2K trades, the wait between VCP detection and breakout
trigger carries no information about subsequent excess vs SPY. The S&P pooled
difference is +0.23 pp (t 0.12, a coin flip: bootstrap P(diff>0) = 55.3%), the
S&P folds and trims flip sign, and rank correlation between latency and excess
is indistinguishable from zero in both universes. R2K is directionally positive
but never approaches significance. The give-up criteria fired on round 1; the
hypothesis is buried.

## 1. Performance Metrics (conditioning slices, excess vs SPY)

| Universe / slice | n fresh | n stale | mean fresh | mean stale | diff (pp) | Welch t | p |
|---|---:|---:|---:|---:|---:|---:|---:|
| **S&P pooled (frozen ≤7d)** | 136 | 48 | −0.38 | −0.61 | +0.23 | +0.12 | 0.901 |
| S&P fold 2016–2020 | 45 | 18 | +0.37 | −0.85 | +1.22 | +0.38 | 0.709 |
| S&P fold 2021–2026 | 91 | 30 | −0.75 | −0.47 | **−0.28** | −0.12 | 0.906 |
| S&P drop-top-5 / -10 | — | — | — | — | **−0.27** / +0.88 | −0.16 / +0.59 | 0.87 / 0.55 |
| **R2K pooled (frozen ≤7d)** | 639 | 279 | −0.29 | −0.83 | +0.55 | +0.50 | 0.617 |
| R2K fold 2016–2020 | 247 | 119 | −0.29 | −0.88 | +0.59 | +0.38 | 0.701 |
| R2K fold 2021–2026 | 392 | 160 | −0.28 | −0.80 | +0.51 | +0.34 | 0.736 |

Median latency: 3 days (S&P), 4 days (R2K) — most breakouts trigger fast, so
the stale group is the minority tail. Group quality is uniformly weak (all PFs
0.85–0.95, consistent with programme-wide "entry alpha: none"). Sensitivity
cells (robustness only): S&P flips negative at the 4-day split; R2K stays
positive everywhere (best cell 14d, t 1.39, ns).

## 2. Statistical Significance

- Primary (S&P) declared-direction Welch t **+0.12** (p 0.90). Bootstrap
  (10,000 draws) 90% CI **[−2.87, +3.20]**, P(diff>0) = **55.3%** — a coin flip.
- Continuous check: Spearman(latency_days, excess) = **−0.04** (p 0.59) on S&P,
  **+0.01** (p 0.76) on R2K. No monotone relationship exists; the binary split
  isn't hiding a gradient.
- R2K: t +0.50 (p 0.62), P(diff>0) = 69.8% — directionally consistent,
  statistically nothing.
- Multiplicity: ~trial 188 on this history; any correction is moot for a
  t of 0.12.

## 3. Bias Assessment

| Bias | Status | Evidence |
|---|---|---|
| Lookahead | Absent | Both dates are known at the entry fill; negative latencies (data errors) are dropped — zero occurred |
| Survivorship | **Present** | Current-constituent universes; caps score at 20 |
| Data snooping | Partially mitigated | Direction, 7-day threshold, metric, give-up criteria frozen before results |
| Costs | Not applicable to the difference | Groups share the source log's fill/cost model |
| Base-duration entanglement | Present, declared | Stale entries occur later in the base's life; no correction attempted (moot given the null) |
| Regime overfit | Not applicable | No effect to overfit |

## 4. Robustness

- Fold split: S&P flips sign (+1.22 → −0.28) — the declared criterion fired.
- Outlier trims: S&P flips sign between drop-top-5 (−0.27) and drop-top-10
  (+0.88) — noise.
- Cross-universe: R2K is sign-consistent positive but never significant;
  replicating a coin flip is not replication of an effect.
- Sensitivity: S&P sign-unstable across cells; R2K coherent but ns.
- No true re-optimising walk-forward (cap 55, moot under the 20 cap).

## 5. Red Flags 🚩

1. Primary-sample t of 0.12 with fold and trim sign-flips — as clean a null as
   this pipeline produces.
2. Spearman ≈ 0 in both universes rules out a nonlinear-threshold rescue: there
   is no latency gradient to re-cut.
3. Stale group is thin on S&P (n=48, folds 18/30).
4. Survivorship bias unresolved — caps any score at 20 regardless.

## 6. Improvement Recommendations 💡

1. Do not build any latency filter. Bury the hypothesis.
2. This closes the fourth entry-conditioning family (tape urgency, crowding,
   stop width, latency) — all null or reversed. The trade log's causal fields
   are close to exhausted; further conditioning studies on the same log will
   mostly re-measure noise while inflating the trial count. The honest next
   step for the programme remains new data (survivorship-safe master), not new
   cuts of the same 1,102 trades.
3. Survivorship-safe data remains the only route above 20 for this pipeline.

## 7. Verdict

**6/100 — Reject.** The prespecified give-up criteria fired in round 1 (S&P
|t| < 1.65 plus fold and trim sign-flips), and the Spearman check confirms no
gradient exists at any threshold. Under house rules iteration cannot rescue
this hypothesis, and the survivorship cap binds regardless. Experiment closed
as a null; recorded in CLAUDE.md established results and the memory index.
