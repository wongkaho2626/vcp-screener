# Trial 308–309 — Hard-Stop Survival Classifier

Status: **frozen before fitting/evaluating the internal holdout** on 2026-08-01.

## Hypothesis

High-density forward-return and +10%-winner models failed mainly because too
many selected states hit the unchanged hard stop. Predicting upside mixes two
problems—survival and payoff. A simpler classifier trained only to recognise
whether a candidate can avoid its actually executable hard stop for 20
sessions may remove failed VCP states while preserving enough exposure.

## Frozen model and signals

Use the unchanged fifteen causal daily-state features and purged chronology.
For every fit row, label one if no session low touches the unchanged executable
hard stop during the next 20 sessions and zero otherwise. The stop is the
higher of the frozen pattern stop and 8% below the cost-adjusted next-open
entry. A next open at or below the pattern stop is ineligible, not a survivor.

Fit the existing setup-equal weighted logistic ridge with lambda=10 on
2016-07-01..2018-06-30. Calibration outcomes remain unused. Enter next open
after the first score at or above the 70th percentile of 2019-H1 calibration
scores. Exit at the open after 20 holding sessions unless the unchanged hard
stop exits earlier. No score-decay exit is used.

All PIT S&P 500 membership, adjusted OHLC, fixed cash/sizing/ten-position and
name/sector/ADV caps, costs, 8% risk limit, and benchmark-only SPY controls
remain unchanged. Count the survival target and p70 threshold as two new
multiplicity units, raising 307 -> 309.

Evaluate once on 2020–2021. The rule needs at least 60 trades, CAGR at least
15%, Sharpe at least 0.75, PF above 1.20, MDD better than -15%, and positive
drop-top-five expectancy. Failure closes it without formal validation or
untouched OOS.

