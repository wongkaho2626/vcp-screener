# Backtest Verification Report — Fibonacci-Retracement Fill on Pocket Pivot

## Backtest Score: 15 / 100 — Reject

The 38.2% Fibonacci-retracement fill degrades the Pocket Pivot entry on every
dimension that matters: fewer trades, negative expectancy, profit factor below
one, and adverse selection that filters out the winners and keeps the losers.
Confirmed survivorship bias caps the score at 20 regardless; the raw component
total lands below the cap anyway.

| Component | Score | Max |
|---|---:|---:|
| A. Statistical Validity & Significance | 0 | 30 |
| B. Risk-Adjusted Performance | 7 | 25 |
| C. Robustness & Out-of-Sample | 8 | 25 |
| D. Trade Quality & Consistency | 0 | 20 |
| **Raw total** | **15** | **100** |
| Caps applied | Confirmed survivorship bias → 20; <30 independent trades → 40; no true walk-forward → 55 | |
| **Final score** | **15** | **100** |

## Frozen hypothesis (declared before the run)

Keep the frozen Pocket Pivot v2 signal; replace its next-open fill with a wait
for the canonical 38.2% Fibonacci retracement of the signal leg (lowest low of
the 10 sessions ending at the signal bar, up to the signal bar's high). Fill
next open after the first bar that touches the level and closes at or above it
(touch-and-hold, mirroring the validated MA20 structure). Invalidate on a close
below the frozen last-contraction low; no touch within 10 sessions means no
trade. Retracement 50%/61.8% and wait windows 5/15 computed as robustness only.
No threshold sweep. `forward_outcome` never consulted.

Inputs identical to the Pocket Pivot v2 run: detections from
`backtests/csv_full/vcp_backtest_2026-07-09_235123.json`, prices from
`SP500_Historical_Data.csv` (`data_source == "csv"` verified in lineage).

## Executive summary

Of 42 Pocket Pivot signals, only 19 retraced to the 38.2% level and filled;
the other 23 — including six of the seven trades that made more than +10% as
plain pocket pivots (GRMN +30.6%, GDDY +27.6%, TECH +13.7%, PFG +11.3%, DOV
+11.1%, MA +11.0%) — ran away without touching the level. The one large winner
that did retrace (ALGN, +62.9% as a pocket pivot) filled late on 2020-09-22 and
was stopped out two days later at −8.1%. The mechanism is textbook adverse
selection: momentum entries that pull back deeply enough to offer a "better
price" are disproportionately the ones already failing.

## 1. Performance metrics (full period, net of 10 bps/side)

| Metric | pullback | pocket_pivot | pocket_pivot_fib |
|---|---:|---:|---:|
| Trades | 197 | 42 | 19 |
| Total return | −5.41% | +8.53% | −0.28% |
| CAGR | −0.53% | +0.79% | −0.03% |
| Sharpe / Sortino | −0.12 / −0.16 | 0.38 / 0.69 | −0.02 / −0.03 |
| Max drawdown | −15.92% | −3.74% | −2.34% |
| Avg gross exposure | 14.5% | 3.8% | 1.3% |
| Profit factor | 1.01 | 1.32 | 0.75 |
| Win rate / payoff | 34.5% / 1.92 | 31.0% / 2.94 | 21.1% / 2.80 |
| Expectancy per trade | +0.04% | +1.20% | −0.93% |
| Exposure-matched excess CAGR | −2.15% | −0.08% | −0.08% |

## 2. Statistical significance

- Raw daily return: t = −0.072, PSR 47.1% — no evidence of positive drift.
- Exposure-matched excess: t = −0.312, PSR 37.9%.
- Paired daily lift vs plain pocket_pivot: t = **−1.44** (−0.83%/yr annualised)
  — directionally *harmful*, not merely null.
- Paired matched-excess lift vs pullback: t = +2.20, but this is an artefact of
  near-zero exposure (1.3%) against a losing baseline, not stock-selection
  alpha; the strategy's own excess return is negative.
- 10-day block-bootstrap 90% CIs: raw CAGR [−0.51%, +0.44%], matched-excess
  [−0.45%, +0.27%] — both centred on zero.
- 19 trades is below the 30-trade adequacy floor; every trade-level statistic
  is fragile by construction.

## 3. Bias assessment

| Bias | Status | Evidence |
|---|---|---|
| Lookahead | Absent | Level frozen at the signal bar from prior/contemporaneous OHLCV; touch-and-hold evaluated forward; next-open fill; `forward_outcome` unused |
| Survivorship | Present — fatal | Current-constituent CSV, no delisted names |
| Data snooping | Present, penalised | Rule prespecified with canonical 38.2%, but ~180+ prior trials on this history |
| Cost underestimate | Partially addressed | 10 bps/side baseline; turnover lower than v2, cost stress not repeated (immaterial at PF 0.75) |
| Regime overfit | Present | Development +0.80% → validation +0.70% → evaluation −1.47% (0 winners) |

## 4. Robustness (computed, not adopted)

| Variant | Trades | Return | Sharpe | PF |
|---|---:|---:|---:|---:|
| Frozen 38.2%, wait 10 | 19 | −0.28% | −0.02 | 0.75 |
| Retracement 50% | 15 | −0.51% | −0.10 | 0.47 |
| Retracement 61.8% | 13 | +0.03% | +0.01 | 0.63 |
| Wait window 5 | 11 | +2.30% | +0.26 | 1.62 |
| Wait window 15 | 23 | −2.01% | −0.20 | 0.56 |

Signs flip across neighbouring cells on single-digit trade counts — noise, not
a surface. The 70/30 chronological split gives IS Sharpe −0.06 / OOS +0.07:
nothing to transfer.

## 5. Red flags 🚩

1. Adverse selection is structural, not incidental: waiting for a discount on
   a momentum signal preferentially fills the failing setups. Deeper
   retracement levels (50%, 61.8%) make PF *worse*, confirming the mechanism.
2. The single biggest v2 winner (ALGN +62.9%) became a −8.1% loss under the
   fib fill.
3. Profit factor 0.75 with 21% win rate: negative expectancy before any
   robustness question arises.
4. 19 trades in 10 years at 1.3% exposure — economically negligible.
5. All v2 caveats (survivorship, synthetic benchmark, missing sectors) carry
   over unchanged.

## 6. Recommendations 💡

1. Do not pursue Fibonacci retracement fills on Pocket Pivot signals; the
   pocket pivot thesis (institutional accumulation) is contradicted by waiting
   for weakness. Record the null and stop.
2. This mirrors the established edge×pullback interaction null: retrace-style
   improvements and momentum-signal entries are substitutes, not complements.
   The validated MA20 pullback works on *breakout* entries, and porting the
   same structure onto Pocket Pivot fails — structure does not transfer.
3. Any future entry-timing idea should first check the fill-rate/winner-miss
   trade-off on the 42 v2 signals before a full portfolio run.

## 7. Verdict

**15/100 — Reject.** The Fibonacci retracement fill turns a marginal relative
improvement (Pocket Pivot v2, itself 20/100 Reject) into an outright negative-
expectancy rule by systematically missing the winners and catching the losers.
Null recorded; nothing here justifies further parameter exploration on this
data.
