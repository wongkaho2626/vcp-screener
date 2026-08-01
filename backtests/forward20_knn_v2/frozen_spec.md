# Trial 300–302 — Setup-Balanced Forward-20 Analogues

Status: **frozen before fitting/evaluating holdout outcomes** on 2026-08-01.

## Hypothesis

The linear, squared, and logistic timing models cannot express local
interactions among setup age, pivot/stop geometry, multi-horizon returns,
close location, volume, volatility, and Edge Rank. A setup-balanced nearest-
analogue estimator can recognise recurring causal states without fitting a
large parametric model or letting the many daily rows from one setup dominate.

Use the unchanged fifteen causal features and hard-stop-aware forward-20 net
return labels from the purged 2016-07-01..2018-06-30 fit period. Standardise
features using fit rows only. For each scored row:

1. within each of the 103 fit setups, find the single closest daily state by
   Euclidean distance in standardised feature space;
2. take the 15 closest distinct setups (`round(sqrt(103))`); and
3. predict the uniform mean label of those fifteen analogue states.

There is no outcome-selected distance weighting, feature selection, or tuned
`k`. Calibrate thresholds without outcomes on the existing 2019-H1 rows. Enter
next open after the first score at or above calibration p80; exit next open
after a later score at or below calibration p50. The hard stop and 60-session
timeout remain active and can exit earlier.

Keep PIT S&P 500 membership, adjusted OHLC, fixed portfolio sizing/cash/
capacity, sector/name/ADV constraints, 8% entry-risk cap, commissions,
slippage, and benchmark-only SPY unchanged. Count the analogue estimator,
fixed k=15, and p80 threshold as three new multiplicity units, raising 299 ->
302.

Evaluate once on 2020–2021. The gate is at least 40 trades, CAGR at least 15%,
Sharpe at least 0.75, PF above 1.20, MDD better than -15%, and positive
drop-top-five expectancy. Failure closes the model without formal validation
or untouched OOS.

