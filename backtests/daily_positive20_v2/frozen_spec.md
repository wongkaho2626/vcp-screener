# Trial 310–311 — Positive Forward-20 Classifier

Status: **frozen before fitting/evaluating internal-holdout outcomes** on
2026-08-01.

The forward-20 linear regression retained robust but sparse high-score trades;
the +10% winner classifier was too imbalanced, while the stop-survival
classifier selected safe but unprofitable states. The intermediate causal
question is whether the fixed, hard-stop-aware 20-session net outcome is simply
positive. Binary classification removes sensitivity to winner magnitude
without restricting positives to rare double-digit returns.

Use the unchanged fifteen features, setup-equal logistic ridge (lambda=10),
purged 2016-07-01..2018-06-30 fit, and outcome-free 2019-H1 calibration. Label
fit rows one when the cost-adjusted fixed-20/hard-stop return is greater than or
equal to zero and zero otherwise. Enter next open after the first score at or
above calibration p70. Exit at the open after 20 holding sessions unless the
unchanged hard stop exits earlier.

PIT S&P 500 membership, adjusted prices, fixed sizing/cash/capacity, sector/
name/ADV constraints, 8% risk cap, costs, and benchmark-only SPY remain fixed.
Count the zero-return binary target and p70 threshold as two multiplicity units,
raising 309 -> 311.

The one 2020–2021 internal holdout requires at least 60 trades, CAGR at least
15%, Sharpe at least 0.75, PF above 1.20, MDD better than -15%, and positive
drop-top-five expectancy. Failure closes the rule without formal validation or
untouched OOS.

