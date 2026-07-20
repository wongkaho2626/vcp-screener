# Backtest Verification Report — pullback_pit2016 (2016-2026 PIT re-measurement of the shipped MA20 pullback overlay)

Evaluated: 2026-07-21 · backtest-analyst · round 1 (final — no iteration needed)
Inputs: `frozen_spec.md` (declared 2026-07-20, pre-results, incl. the dated
pre-results alias amendment), `pullback_oos_2026-07-21_002134.{md,json}`
(196 paired records), `vcp_backtest_2026-07-21_002109.json` (1,053 detections,
600-ticker delisted-inclusive universe), `coverage.json` (91.39% member-day
coverage). Note: the experiment report's header line cites the pullback_oos
spec path (hardcoded in `build_report`); the governing spec for this run is
`backtests/pullback_pit2016/frozen_spec.md`.

## Backtest Score: 68 / 100 — Promising. **First uncapped score in the programme.**

The shipped MA20 pullback overlay **passes its predeclared bar under PIT
discipline on its own era**: paired Δ +0.98 pp (t 2.73, n 196), both folds
positive, trim signs hold. The improvement is real — not a survivorship
artifact — but it is roughly **58% smaller than the survivor-only number**
(+2.35 → +0.98), its pre-2016 OOS replication failed, and it has faded since
2022. 68 is exactly what "real but shrunken, regime-dependent execution
improvement" should score.

| Component | Score | Max |
|---|---|---|
| A. Statistical Validity & Significance | 25 | 30 |
| B. Risk-Adjusted Performance | n/a — redistributed | 25 |
| C. Robustness & Out-of-Sample | 12 | 25 |
| D. Trade Quality & Consistency | 14 | 20 |
| **Raw total (reduced basis A+C+D = 75)** | **51/75 → 68/100** | |
| Caps applied | **none** — survivorship cap lifted (coverage 91.39% ≥ predeclared 90%); an OOS segment exists (2006-15 PIT, failed — priced into C) | |
| **Final score** | **68** | 100 |

## Executive Summary

This experiment answers the question left open by the pullback_oos reversal:
is the shipped overlay's 2016-2026 evidence also a survivorship artifact?
**No.** On a 600-ticker delisted-inclusive PIT universe (91.4% member-day
coverage, membership-gated detections, delisted-inclusive benchmark), the
paired improvement survives at +0.98 pp (t 2.73, PSR 99.4%, DSR 92.5% under
the 4-variant selection framing, bootstrap P(Δ≤0) 0.31%). But PIT discipline
cuts the effect by more than half, the 2021-2026 fold alone is a coin flip
(+0.33, t 0.75), and the only true OOS test (2006-2015 PIT) failed. The
overlay keeps its place as a live execution overlay at a corrected, more
modest effect size; it is not, and has never been, alpha.

## 1. Performance Metrics (paired Δ = pullback excess − breakout excess, pp)

| Metric | Value | Threshold | Status |
|---|---|---|---|
| n pairs | 196 | ≥30 | ✅ |
| Mean Δ | +0.983 | >0 declared | ✅ |
| t / t_adj (n_eff 171) | 2.73 / 2.55 | ≥2 declared | ✅ |
| 95% bootstrap CI | [+0.26, +1.67] | excludes 0 | ✅ |
| Median / Win% | +0.82 / 64.8% | >0 / >50% | ✅ |
| Δ profit factor | 1.85 | >1.5 | ✅ |
| Fold 2016H2-2020 | +2.17 (t 3.42, n 63) | same sign | ✅ |
| Fold 2021-2026 | +0.33 (t 0.75, n 128) | same sign | ✅ (weak) |
| Drop-top-5 / 10 | +0.59 (t 1.87) / +0.37 (t 1.20) | sign holds | ✅ sign, ⚠️ significance |
| Skew / excess kurtosis | −0.44 / +9.77 | — | fat tails |
| Survivor-only baseline (same code path) | +2.35 (t 4.52, n 96) | — | PIT cuts effect 58% |
| Context: breakout / pullback abs. excess | −1.20 / −1.97 | — | no standalone alpha |

## 2. Statistical Significance

t 2.73 (one-sided p ≈ 0.003); n_eff 171 (ρ₁ 0.07) → t_adj 2.55; PSR 99.4%;
DSR 92.5% at N=4 (the honest selection family — the rule won a 4-variant scan
on this era) and 72.3% at N=20; bootstrap P(Δ≤0) 0.31%. The in-sample-winner
discount is the key one: this is a re-measurement of a rule selected on this
decade, so t 2.73 confirms the original effect at corrected size — it is not
a fresh discovery.

## 3. Bias Assessment

| Bias | Status | Evidence |
|---|---|---|
| Survivorship | **Resolved for this era (predeclared threshold met)** | 720-name PIT union; 600 with usable prices; 91.39% member-day coverage (82.5% in 2016 rising to 98.7% in 2026); membership gate dropped 56 non-member detections; benchmark equal-weights the delisted-inclusive universe. Residual 8.6% missing member-days concentrate in 2016-2018 delistings purged by Yahoo — direction unknowable but bounded. |
| Lookahead | Absent | Same tested machinery as prior rounds (truncation-invariance test; membership is public info at as_of_date). |
| Data quality | Clean | Scale-break screen: zero corrupt series; benchmark extremes −12.7%/+11.8% (COVID days) — passes the predeclared ±15% sanity gate. |
| Snooping | Absent for this run | Spec + folds + alias policy frozen pre-results (one dated pre-results alias amendment, disclosed in the spec); zero rule parameters changed; losing variants not re-run. |
| In-sample selection | **Present, inherent, disclosed** | The rule was developed on this era; this experiment measures bias-corrected size, not out-of-sample validity. The OOS verdict remains the failed 2006-2015 PIT test. |

## 4. Robustness

- **True OOS**: failed (pullback_oos, 2006-15 PIT: Δ +0.22, t 0.58).
  Efficiency (OOS/IS per-pair SR) 0.050/0.195 = **0.26** — below the 0.3
  overfit line. This is the main thing keeping the score out of the 80s.
- **Regime**: 2016-2021 positive every year (+1.1 to +3.2 pp); 2022-2025
  flat-to-negative (−0.6 to +0.2); 2026 +1.0. 8/11 years positive. The
  improvement is a trending-tape phenomenon and has largely faded since 2022
  — same asymmetry seen in every prior cut.
- **Trims**: sign robust, significance decays (t 1.87 → 1.20); median stable
  ≈ +0.7-0.8; kurtosis 9.8 says a few large pairs carry part of the mean.
- **Cross-universe**: no PIT R2K data — not runnable (recorded; the 2016-2026
  survivors-only R2K replication of the original experiment stands as weaker
  supporting evidence).
- **Parameter sensitivity**: not re-scanned (anti-snooping, frozen); original
  4-variant surface was smooth; trim-stable median argues against knife-edge.

## 5. Red Flags 🚩

1. **OOS failure stands** — the one true out-of-sample test of this rule
   (2006-2015 PIT) is a null. What survives here is era-local evidence.
2. **Post-2021 fade** — the 2021-2026 fold is +0.33 (t 0.75); on the most
   recent 4 years the overlay is indistinguishable from noise.
3. **Effect size correction** — survivor-only numbers overstated the
   improvement ~2.4×; any sizing intuition built on +1.4 to +2.3 pp should be
   reset to ≈ +1 pp, likely less live.
4. Fat tails (kurtosis 9.8) + trim decay — the mean leans on big winners;
   the median (+0.8) is the safer summary.

## 6. Recommendations 💡

1. **Keep the overlay live, with corrected expectations** (≈ +1 pp per
   avoided chase, median +0.8, fading regime) — the frozen spec's demotion
   trigger did not fire.
2. The only evidence that could move this above ~80: genuine forward
   validation — let the live overlay accumulate prospective trades (the spec
   register pattern), or a PIT R2K universe for cross-universe replication.
3. Do not re-tune on 2016-2026; the era is now doubly mined (development +
   this re-measurement).

## 7. Verdict

**68/100 — Promising (uncapped).** The predeclared bar was met in full:
Δ > 0 (+0.98), t ≥ 2 (2.73, adj 2.55), both folds positive, trim signs hold —
so the shipped MA20 pullback overlay's improvement on its own era is real,
not a survivorship artifact, at roughly 42% of its survivor-only size. It
remains an execution improvement on a no-alpha signal, weakest in recent
years, with a failed OOS decade behind it. Deploy-grade (80+) would require
prospective forward evidence, not more history.
