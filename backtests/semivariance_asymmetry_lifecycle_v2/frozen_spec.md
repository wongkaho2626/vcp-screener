# Trial 441–447 — Realized Semivariance Asymmetry Lifecycle

Status: **frozen before discovery density, return, validation or best-available
OOS evaluation** on 2026-08-01.

## Hypothesis and prior evidence

Total volatility, range expansion, path efficiency, fitted trend quality,
directional movement, extreme recency and range-midpoint equilibrium have
failed. Realized semivariance asymmetry asks a different question: whether the
squared energy of positive close-to-close returns dominates the squared energy
of negative returns, irrespective of their time ordering or the final endpoint.
A VCP continuation with upside variation at least 50% greater than downside
variation may distinguish constructive price discovery from symmetric noise.

This is not a volatility-size filter, return ranking or smoothness measure. The
broad negative price-state prior is disclosed. One fixed 20-session ratio with
fixed hysteresis is used; no period or threshold scan is allowed.

## Frozen causal rule

At each completed session calculate the 20 simple close-to-close returns ending
on that session. Define:

- upside energy = sum of squared strictly positive returns;
- downside energy = sum of squared strictly negative returns;
- asymmetry ratio = upside energy / downside energy.

If downside energy is zero and upside energy is positive, the ratio is positive
infinity. If both energies are zero, the ratio is undefined and cannot trigger
entry or failure.

For each PIT-eligible frozen VCP setup:

1. enter when the asymmetry ratio is at least 1.50 and current close is strictly
   above the frozen pivot;
2. fill at the next session's open;
3. define asymmetry failure when the ratio is strictly below 0.75;
4. exit at the next open after two consecutive later completed sessions in
   asymmetry failure;
5. after exit require a later qualifying state and permit at most three
   attempts per setup.

The unchanged frozen pattern stop and 60-session maximum hold can exit earlier.
All returns end at the signal/exit close. Fixed Edge Rank sizing, initial
capital, position/name/sector/ADV limits, 8% risk cap, commission, slippage and
cash treatment remain unchanged. SPY is benchmark-only and can never be held.

## Density and multiplicity

Before return evaluation, count discovery signals after the exact lifecycle
but before portfolio rejection. Continue only for 80 through 500 signals. A
density failure records counts only and opens no return or later partition.

Count the 20-return window, sign-separated squared energy, 1.50 entry ratio,
frozen-pivot confirmation, 0.75 failure ratio, two-close exit and three-attempt
lifecycle as seven new multiplicity units, increasing declared evaluated
trials from 440 to 447.

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
