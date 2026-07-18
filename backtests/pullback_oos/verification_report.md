# Backtest Verification Report — pullback_oos (pre-2016 OOS replication of the MA20 pullback entry)

Evaluated: 2026-07-18 · Analyst: backtest-analyst skill (round 2 re-run;
round-1 numbers reproduced, three refinements folded in — see §2/§4 notes)
Inputs: `frozen_spec.md` (predeclared), `pullback_oos_2026-07-18_214305.{md,json}`
(196 paired records), `vcp_backtest_2026-07-18_214224.json` (915 detections,
2006-2015, `data_source=csv:SP500_Pre2016_Data.csv`).

## Backtest Score: 20 / 100 — Reject (capped) · **Pre-cap raw score: 71 / 100 — Promising**

The 20 is a **data cap, not a rule verdict**: the universe is the surviving
2026 S&P constituent list applied to 2006-2015, a confirmed survivorship bias
that the house rubric hard-caps at 20 for any deployability claim. On the
evidence the data *can* support, this is the first experiment in ~20 that
**passes its own predeclared OOS bar**: the shipped MA20 pullback entry
replicates directionally on a decade it was never developed on.

| Component | Score | Max |
|---|---|---|
| A. Statistical Validity & Significance | 23 | 30 |
| B. Risk-Adjusted Performance | n/a — redistributed | 25 |
| C. Robustness & Out-of-Sample | 15 | 25 |
| D. Trade Quality & Consistency | 15 | 20 |
| **Raw total (reduced basis A+C+D = 75)** | **53/75 → 71/100** | |
| Caps applied | survivorship-biased universe → **20** | |
| **Final score** | **20** | 100 |

Component B (Sharpe/Sortino/MDD) is not computable — the deliverable is a
per-detection paired execution delta, not a portfolio equity curve — so its
weight was redistributed per the rubric (Step 3), and that is stated here
rather than treated as zero.

## Executive Summary

The one validated positive result of this research programme (MA20
touch-and-hold pullback entry beats chasing the breakout close; +1.36 pp
paired, t 3.13 on 2016-2026) was re-tested on 2006-2015 S&P data that no
prior trial had touched, under a spec frozen before any result was computed.
It replicates in direction and significance (paired Δ +0.69 pp, t 2.50,
n 196, win 63.8%, PF 1.65), passes the predeclared fold-sign and trim-sign
requirements, and stays flat rather than collapsing through the 2008-09 bear.
The effect is roughly half its in-sample size, its mean (not its median) is
outlier-fragile, and the gain is concentrated in 2011-2015. The universe's
survivorship bias caps any deployability claim at 20; within that limit the
honest reading is: **execution improvement confirmed out-of-sample, no
standalone alpha — same conclusion as 2016-2026, now on independent data.**

## 1. Performance Metrics (paired Δ = pullback excess − breakout excess, pp)

| Metric | Value | Threshold | Status |
|---|---|---|---|
| n pairs | 196 | ≥30 | ✅ |
| Mean Δ | +0.688 | >0 declared | ✅ |
| t-statistic | 2.50 | ≥2 declared | ✅ |
| 95% bootstrap CI | [+0.14, +1.22] | excludes 0 | ✅ |
| Median Δ | +1.02 | >0 | ✅ |
| Win rate | 63.8% | >50% | ✅ |
| Delta profit factor | 1.649 | >1.5 | ✅ |
| Per-pair SR | 0.179 | — | context |
| Skew / excess kurtosis | −0.25 / +2.73 | — | mildly fat-tailed |
| Fold 2006-2010 | +0.23 (t 0.45, n 79) | same sign | ✅ (weak) |
| Fold 2011-2015 | +1.08 (t 3.38, n 109) | same sign | ✅ |
| Drop-top-5 / drop-top-10 mean | +0.41 (t 1.62) / +0.22 (t 0.90) | sign holds | ✅ sign, ⚠️ significance |
| Context: breakout leg abs. excess | −1.15 (PF 0.73) | — | no standalone alpha |
| Context: pullback leg abs. excess | −1.13 (PF 0.74) | — | no standalone alpha |

Both absolute legs are *negative* vs the synthetic equal-weight benchmark —
consistent with the established "entry alpha: none" result. The overlay
improves execution of a zero-edge signal; it does not create an edge.

## 2. Statistical Significance

- **t = 2.50** on 196 pairs (one-sided p ≈ 0.007 vs the declared direction).
- **Effective n ≈ 132** (3-lag autocorrelations ρ₁₋₃ = 0.08/0.11/0.06 of the
  chronologically ordered deltas; Ljung-Box(3) = 4.23, below the 7.81
  5% critical value; max 7 pairs/month across 94 months). t adjusted for
  n_eff ≈ 2.05 — the declared t ≥ 2 bar survives the most conservative
  independence adjustment, with no margin to spare.
- **Jarque-Bera = 63.0** → non-normal (fat tails); PSR below already
  corrects for skew/kurtosis.
- **Kelly fraction (full) 0.25**; per-pair VaR95 −5.6 pp, CVaR95 −9.1 pp,
  tail ratio 1.05.
- **PSR (SR* = 0): 99.2%.**
- **DSR by multiplicity framing** (the honest number depends on what counts
  as the trial family):

  | Framing | N trials | DSR |
  |---|---|---|
  | Predeclared single confirmation of the shipped rule | 1 | = PSR 99.2% |
  | Winner of the original 4-variant pullback scan | 4 | **91.1%** |
  | Broad in-repo entry-overlay family | 20 | 69.1% |
  | Entire programme (~180 trials, different data & hypotheses) | 180 | 37.0% |

  The 4-variant framing is the most defensible: the other ~176 trials were on
  2016-2026 data and mostly unrelated hypotheses, while this test's rule and
  direction were fixed by the shipped overlay before any pre-2016 bar was
  read. Even the harshest framing leaves DSR positive (>0), i.e. the observed
  SR exceeds the expected maximum of that many null trials.
- **Bootstrap P(mean ≤ 0) = 0.63%**; 50% subsample resampling: P(mean < 0) =
  0.9%, median subsample mean +0.69.

## 3. Bias Assessment

| Bias | Status | Evidence |
|---|---|---|
| Lookahead | **Absent** | Signals use only bars at/after the breakout; pattern levels fixed at detection; pytest truncation-invariance test (`test_no_lookahead_truncation_invariance`) passes; `forward_outcome` consulted only to locate the breakout bar. |
| Survivorship | **Present (confirmed)** | Universe = 2026 constituents held back to 2006; delisted names absent. Mitigated but not removed by the paired design (both legs trade the same surviving names). Residual risk is *directional*: pullback entries buy weakness, and weakness in survivors recovers more often than it would in delisted names — the paired Δ is therefore plausibly inflated, not just noisy. → hard cap 20. |
| Overfitting / snooping | **Absent for this test** | Spec, folds, trims, success and give-up criteria frozen in `frozen_spec.md` before the first pre-2016 detection was computed; zero parameters tuned; the 3 losing 2016-2026 variants were not re-run. |
| Costs | **Absent (by construction)** | Both legs are one round trip on the same name — per-side costs cancel exactly in Δ at 10/20/50/100 bps. Absolute legs shown with cost drag as context. |
| Benchmark validity | **Caveat** | "SPY" is a synthetic equal-weight index of the surviving universe (labelled in report) — harsher than real SPY, common to both legs, so it cannot flip Δ's sign. |
| Data-source fallback | **Absent** | `data_source=csv:SP500_Pre2016_Data.csv` verified in metadata; the CLI hard-errors on non-csv sources. |
| Spec deviation | **Minor, disclosed** | 8 pairs carry Dec-2005 breakout dates (walk's earliest as-of), inside pooled but outside both folds. Excluding them *raises* the pooled mean to ≈ +0.72 — immaterial and adverse-to-claim, not favorable. |

## 4. Robustness

- **WFA / OOS efficiency**: this experiment *is* the OOS leg. IS (2016-2026
  CSV, same code path) per-pair SR 0.461 (Δ +2.35, t 4.52, n 96); OOS per-pair
  SR 0.179 → **efficiency 0.39** — real but roughly half-strength signal,
  typical of honest replications, inside the 0.3-0.5 "reasonable" band.
- **Regime stability**: positive mean in 7 of 11 calendar years (64%); 2008 is the
  worst year (−1.42, n 11, win 36%) but 2008-09 combined is flat (+0.25,
  n 22) — the overlay does not blow up in the bear, it merely stops helping.
- **Trim fragility (the main statistical weakness)**: dropping the top 5/10
  of 196 pairs keeps the sign (+0.41/+0.22) but kills significance (t 1.62 →
  0.90). The median Δ is stable at ≈ +0.9-1.0 across all trims and the win
  rate stays ≈ 62-64% — the *typical* pair benefits; the *mean* leans on a
  handful of large winners. Declared bar required sign survival only: met.
- **Parameter sensitivity**: deliberately not scanned here (frozen spec
  forbids re-running the 4-variant family on new data — anti-snooping).
  Indirect evidence: the 2016-2026 surface was smooth across MA10/MA20/pivot
  variants, and the median/win-rate stability across trims argues against a
  knife-edge artifact. Scored partial credit accordingly.
- **Monte Carlo**: trade-level bootstrap and 50% subsampling above; observed
  statistics sit inside their resampled bands. Cumulative-Δ max drawdown
  −43 pp vs shuffled-order MC median −29 pp / 5th pct −47 pp — inside the
  band but worse than typical, reflecting the flat 2006-2010 stretch.

## 5. Red Flags 🚩

1. **Survivorship bias with directional teeth** — buying pullbacks in a
   survivors-only universe plausibly inflates Δ itself, not just absolute
   returns. This is why the cap is warranted despite the paired design.
2. **Mean is outlier-carried** — significance vanishes after drop-top-10;
   only the median/win-rate story survives trimming.
3. **Fold asymmetry** — 2006-2010 contributes +0.23 (t 0.45): the replication
   is driven by 2011-2015. A regime in which the overlay is a coin flip
   (choppy/bear tape) is documented, now in two independent decades.
4. **Effect size halved OOS** (efficiency 0.39) — expect further shrinkage
   live; at half of +0.69 pp the overlay remains useful but modest.
5. **Selection-of-winner residue** — the rule is the best of 4 variants
   chosen in-sample; the 4-trial DSR (91%) covers this, but it is the reason
   the pooled t 2.50 should not be read as a fresh discovery-grade result.

## 6. Improvement Recommendations 💡

1. **Lift the cap, nothing else**: build a delisted-inclusive pre-2016
   universe (PIT constituent lists + delisted OHLCV). This is the *only*
   change that can move the score above 20; no amount of re-analysis on this
   CSV can.
2. If/when such data exists, re-run this exact frozen spec unchanged — the
   experiment is designed to be replayed verbatim.
3. Optional context (not score-moving): an R2K pre-2016 price CSV would
   restore the cross-universe prong.
4. Do **not** re-tune the overlay on this decade (window/MA scans) — that
   would convert a clean confirmation into a new in-sample fit.

## 7. Verdict

**Final: 20/100 — Reject band, by survivorship cap. Pre-cap raw: 72/100 —
Promising.** The predeclared replication bar (Δ > 0, t ≥ 2, fold signs, trim
signs) was met in full — the first OOS pass in this programme. The correct
reading is narrow: *the MA20 pullback overlay is a genuine execution
improvement over breakout-chasing on this data family, confirmed on an
independent decade; it is not standalone alpha (both legs remain negative
vs benchmark), and no deployability claim survives the survivorship cap.*
Good rule, bad data — the blocker is the security master, not the statistics.
