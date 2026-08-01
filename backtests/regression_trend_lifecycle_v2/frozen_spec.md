# Trial 418–424 — Log-Price Regression Trend-Quality Lifecycle

Status: **frozen before discovery return, validation or best-available OOS
evaluation** on 2026-08-01.

## Hypothesis and prior evidence

Signed path efficiency, DMI, PSAR, MACD and several moving-average rules have
failed. A rolling log-price regression is mechanically different from endpoint
efficiency: it preserves the time ordering of every close, estimates a
compounded trend slope, and measures how much path variation that ordered trend
explains. A positive, majority-explaining trend above the VCP pivot may isolate
orderly continuation; loss of both direction or fit supplies a causal exit.

The extensive negative trend-family prior is disclosed. This is one fixed
parameterisation with no threshold or lookback scan.

## Frozen causal rule

For each completed session, regress the natural logarithm of the most recent 20
positive closes, including the current close, on integer time `0..19` using
ordinary least squares. Calculate the fitted slope and ordinary R-squared.

For each PIT-eligible frozen VCP setup:

1. enter when slope is strictly positive, R-squared is at least 0.50, and
   current close is strictly above the frozen pivot;
2. fill at the next session's open;
3. define trend failure when slope is non-positive or R-squared is below 0.20;
4. exit at the next open after two consecutive later completed sessions in
   trend failure;
5. after exit require a later qualifying state and permit at most three
   attempts per setup.

The unchanged frozen pattern stop and 60-session maximum hold can exit earlier.
All regression observations end at the signal/exit close. Fixed Edge Rank
sizing, initial capital, position/name/sector/ADV limits, 8% risk cap,
commission, slippage and cash treatment remain unchanged. SPY is benchmark-only
and can never be held.

## Density and multiplicity

Before return evaluation, count discovery signals after the exact lifecycle
but before portfolio rejection. Continue only for 80 through 500 signals. A
density failure records counts only and opens no return or later partition.

Count the 20-session log-price window, OLS slope direction, 0.50 entry R²,
pivot confirmation, slope-or-0.20-R² failure state, two-close exit and
three-attempt lifecycle as seven new multiplicity units, increasing declared
evaluated trials from 417 to 424.

## Frozen chronology and gates

- discovery/train: 2016-07-01 through 2018-06-30;
- embargo: 2018-07-01 through 2018-12-31;
- validation: 2019-01-01 through 2021-12-31;
- capped best-available OOS: 2022-01-01 through 2026-03-31.

Train requires >=60 trades, CAGR >=10%, Sharpe >=0.75, PF >1.20, MDD better
than -15%, and positive drop-top-five expectancy. Only a complete pass opens
validation, which requires >=60 trades, CAGR >=15% and the same quality gates.
Only a validation pass may open the unchanged OOS; OOS success requires >=20%
net CAGR and >=30 independent trades.

All periods are contaminated by prior research and must not be described as
untouched. Reports must show raw A/B/C/D, every applicable survivorship/OOS cap
and final score. Missing 2000–2005 data is out of scope.
