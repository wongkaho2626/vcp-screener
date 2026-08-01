# Trial 305–307 — Last-Contraction Undercut and Rally

Status: **frozen before evaluating train or internal-holdout returns** on
2026-08-01.

## Hypothesis

A textbook VCP shakeout can briefly run stops below the last contraction low
without invalidating the base, then recover that level by the close. Existing
experiments tested closing lows, five-day-low reversals, pivot reclaims, and
standing limit orders, but not an intraday undercut of the frozen contraction
low paired with a newly observable shakeout stop.

## Frozen entry and exit

For each PIT-eligible daily VCP detection, inspect at most the following 60
sessions and select the first bar that satisfies all conditions:

- no earlier close since detection has closed below the original last-
  contraction low;
- the session low is strictly below that frozen low but no more than 2% below;
- the close recovers to at least the frozen low; and
- close location value `(close-low)/(high-low)` is at least 0.50.

Confirm after the close and enter at the next open. Cancel the order if that
open is at or below the shakeout low. Replace the pattern stop with the
shakeout-session low; the unchanged portfolio 8% maximum-risk rule may impose
a tighter stop. Exit at the open after 20 holding sessions unless the hard
stop exits earlier. No same-bar low is used retroactively.

All point-in-time S&P 500 membership, adjusted OHLC, Edge Rank eligibility,
portfolio cash/sizing, ten-position/name/sector/ADV caps, commission, slippage,
and benchmark-only SPY controls remain unchanged.

Count the 2% maximum undercut, 0.50 close-location recovery, and fixed-20 exit
as three multiplicity units, raising the declared total 304 -> 307.

## Sequential gates

First evaluate signals dated 2016-07-01..2018-06-30, with the prespecified
outcome buffer through 2018-12-31. Train must have at least 20 trades, CAGR at
least 10%, Sharpe at least 0.75, PF above 1.20, MDD better than -15%, and
positive drop-top-five expectancy. If it fails, do not access internal-holdout
returns.

Only if train passes, evaluate the unchanged rule once on 2020–2021. Internal
holdout must have at least 30 trades, CAGR at least 15%, the same Sharpe/PF/MDD
requirements, and positive drop-top-five expectancy. Failure closes the rule.
Formal validation and untouched OOS remain sealed unless both gates pass.

