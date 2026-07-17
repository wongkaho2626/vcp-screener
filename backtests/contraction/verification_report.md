# Backtest Verification Report — Contraction-Tightening Sequence Conditioning

## Backtest Score: 7 / 100 — Reject

The declared hypothesis (textbook tightening sequences are better) is not just
absent — it is *reversed*: S&P tight-sequence trades underperform loose ones by
−3.18 pp (Welch t −1.90, bootstrap P(tight>loose) = 3.1%), and the reversal
strengthens under outlier trims. The declared test fails; the reversed reading
is post hoc and only partially replicates.

| Component | Score | Max |
|---|---:|---:|
| A. Statistical Validity & Significance | 4 | 30 |
| B. Risk-Adjusted Performance | n/a (no equity curve — weight redistributed) | 25 |
| C. Robustness & Out-of-Sample | 2 | 25 |
| D. Trade Quality & Consistency | 0 | 20 |
| Raw total (measured basis 75, rescaled to 100) | 6/75 → **8**, judged down to **7** for the incoherent cross-checks | 100 |
| Caps applied | Survivorship bias → 20; no true walk-forward → 55 | |
| **Final score** | **7** | **100** |

Component B is not scored: trade-log conditioning study with no daily equity
curve; weight redistributed per the missing-components rule.

## Executive Summary

First direct test of Minervini's tightening-sequence claim using the detection
metadata (last/first contraction depth ratio, fully formed at `as_of_date`).
On 184 S&P trades the claim fails in reverse: "proper" halving sequences
(ratio ≤ 0.5) average −2.24% excess vs +0.94% for loose sequences (PF 0.58 vs
1.23, win rate 30% vs 45%), and the gap *widens* when top winners are trimmed
(t −2.13 / −2.34). R2K agrees in sign (−0.91 pp) but not significance, its
sensitivity cells flip sign, and Spearman disagrees between universes — so the
reversed effect is S&P-threshold-local, not a coherent gradient. Under the
frozen spec this is a Reject; the reversed pattern joins stop-width in the
"textbook tightness is anti-predictive here" lesson family, as
hypothesis-generating only.

## 1. Performance Metrics (conditioning slices, excess vs SPY)

| Universe / slice | n tight | n loose | mean tight | mean loose | diff (pp) | Welch t | p |
|---|---:|---:|---:|---:|---:|---:|---:|
| **S&P pooled (frozen ≤0.5)** | 80 | 104 | −2.24 | +0.94 | −3.18 | −1.90 | 0.059 |
| S&P fold 2016–2020 | 30 | 33 | −2.18 | +2.03 | −4.21 | −1.55 | 0.129 |
| S&P fold 2021–2026 | 50 | 71 | −2.27 | +0.44 | −2.70 | −1.23 | 0.220 |
| S&P drop-top-5 | 78 | 101 | −3.20 | −0.22 | −2.99 | **−2.13** | 0.035 |
| S&P drop-top-10 | 76 | 98 | −3.90 | −0.87 | −3.03 | **−2.34** | 0.021 |
| **R2K pooled (frozen ≤0.5)** | 318 | 600 | −1.04 | −0.14 | −0.91 | −0.93 | 0.351 |
| R2K folds | — | — | — | — | −0.84 / −0.95 | −0.60 / −0.72 | 0.55 / 0.47 |
| R2K trims | — | — | — | — | −0.46 / −0.26 | −0.52 / −0.31 | 0.60 / 0.76 |

Group quality (S&P): tight PF **0.578**, win 30.0% vs loose PF **1.227**, win
45.2% — the "textbook" group is decisively the worse book. Median ratio 0.515
(S&P) / 0.555 (R2K): the frozen 0.5 threshold splits near the median, so both
groups are well-populated.

Sensitivity (robustness only): S&P stays negative at 0.4 (−2.06) and 0.6
(−1.10) but weakens away from 0.5; **R2K flips sign at both** (+0.87 / +0.10).
Spearman(ratio, excess): S&P **+0.082** (consistent with looser-better, ns);
R2K **−0.034** (opposite its own group difference, ns) — no coherent gradient.

## 2. Statistical Significance

- Declared direction (tight better): decisively failed — the S&P t is −1.90
  *against* the declaration; bootstrap (10,000 draws) 90% CI **[−5.95, −0.39]**,
  P(tight>loose) = **3.1%**.
- Reversed reading (post hoc): S&P is trim-robust (t −2.13 / −2.34 after
  dropping top winners — the reversal is not an outlier artifact) and
  fold-sign-consistent. But R2K is ns (P(diff>0) 17.3%), its sensitivity
  cells flip sign, and the two universes' Spearman signs disagree. A post-hoc
  sign swap also cannot be claimed under the frozen spec, and ~189 prior
  trials apply to any DSR-style correction.
- Sample adequacy: 100% join rate (184/184, 918/918), groups 80/104 and
  318/600 — adequate.

## 3. Bias Assessment

| Bias | Status | Evidence |
|---|---|---|
| Lookahead | Absent | Contraction geometry is complete at `as_of_date`; join is on (symbol, as_of_date); unit tests cover the join and skip rules |
| Survivorship | **Present** | Current-constituent universes; caps score at 20 |
| Data snooping | Partially mitigated | Direction, 0.5 threshold, metric, give-up criteria frozen before results; reversed reading explicitly labelled post hoc |
| Costs | Not applicable to the difference | Groups share the source log's fill/cost model |
| Collinearity with shipped scores | Present, declared | The composite score already weighs VCP-pattern quality; this isolates one component, but tight-sequence trades may differ on other detection attributes — no multivariate control attempted |
| Regime overfit | Not applicable for the declared (dead) direction | Reversed pattern present in both folds |

## 4. Robustness

- Declared effect: absent everywhere — folds, trims, both universes, all
  sensitivity cells. Give-up criteria fired in round 1.
- Reversed effect: S&P fold-consistent and trim-strengthening, but
  threshold-local (weakens at 0.4/0.6), Spearman-incoherent, and R2K
  non-significant with sign-flipping sensitivity cells. It does not meet the
  robustness bar either.
- No true re-optimising walk-forward (cap 55, moot under the 20 cap).

## 5. Red Flags 🚩

1. The core Minervini structural claim, tested directly for the first time,
   points the wrong way on the primary sample — with trim-robust nominal
   significance.
2. The reversal is threshold-local and gradient-free (Spearman ≈ 0), so it
   behaves like a cell effect, not a monotone law — classic overfit shape.
3. Universes disagree on everything except the pooled sign.
4. Survivorship bias unresolved — caps any score at 20 regardless.

## 6. Improvement Recommendations 💡

1. Do not gate on tightening ratio in either direction. Bury the declared
   hypothesis.
2. The reversed pattern ("textbook-perfect tightening is adversely selected
   among detections") now has two independent hints (stop-width, this). If it
   is ever promoted to a real hypothesis, it must be predeclared on new data,
   detection-level (not trade-level), with a multivariate control for the
   other detection attributes and cluster-robust inference.
3. Survivorship-safe data remains the only route above 20 for this pipeline.

## 7. Verdict

**7/100 — Reject.** The prespecified give-up criteria fired in round 1: the
declared direction is not merely insignificant but reversed. The reversed
reading, while trim-robust on S&P, is post hoc, threshold-local,
gradient-free, and unreplicated on R2K — hypothesis-generating only under
house rules. The survivorship cap binds regardless. Experiment closed;
recorded in CLAUDE.md established results and the memory index.
