# Trial 406–411 — OBV Accumulation-Breakout Lifecycle

Status: **frozen before discovery return, validation or best-available OOS
evaluation** on 2026-08-01.

## Hypothesis and prior evidence

Isolated breakout volume, Pocket Pivot and 20-session Chaikin Money Flow rules
all failed. Those tests respectively measure one-day volume, volume relative to
recent down days, or where closes sit within each daily range. On-Balance Volume
(OBV) is still mechanically distinct: it cumulatively assigns full session
volume by close-to-close direction. A fresh OBV high while price confirms above
the VCP pivot may identify persistent net participation rather than a single
volume event.

The prior volume failures lower confidence and are disclosed; this family is
one prespecified test, not a volume parameter scan.

## Frozen causal rule

For each stock, initialise OBV at zero on the first available bar. On each later
completed session add volume if close rose from the preceding close, subtract
volume if it fell, and add zero if unchanged.

For every PIT-eligible frozen VCP setup:

1. current OBV must be strictly above the maximum OBV of the preceding 20
   completed sessions, excluding the current session;
2. current close must be strictly above the frozen VCP pivot;
3. fill at the next session's open;
4. calculate a causal EMA(10) of OBV, seeded by the first ten OBV observations;
5. exit at the next open after two consecutive later completed sessions with
   OBV strictly below its EMA(10);
6. after exit require another fresh 20-session OBV high and permit at most
   three attempts per setup.

The unchanged frozen pattern stop and 60-session maximum hold can exit earlier.
Fixed Edge Rank sizing, initial capital, position/name/sector/ADV limits, 8%
risk cap, commission, slippage and cash treatment remain unchanged. SPY is
benchmark-only and can never be held.

## Density and multiplicity

Before return evaluation, count discovery signals after the exact lifecycle
but before portfolio rejection. Continue only for 80 through 500 signals. A
density failure records counts only and opens no return or later partition.

Count the OBV signed-volume definition, 20-session high, pivot confirmation,
EMA10 exit state, two-close exit confirmation and three-attempt lifecycle as
six new multiplicity units, increasing declared evaluated trials from 405 to
411.

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
