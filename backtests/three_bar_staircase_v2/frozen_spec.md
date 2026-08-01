# Trial 394–399 — Three-Bar Price Staircase Lifecycle

Status: **frozen before discovery return, validation or best-available OOS
evaluation** on 2026-08-01.

## Hypothesis

Single-session breakouts and indicator crossovers have not identified durable
continuation. Three consecutive completed sessions with both higher closes and
higher lows provide a parameter-light observation of persistent demand and
rising support. Requiring the staircase above the VCP pivot, then exiting on a
structural loss of the prior two lows, may distinguish orderly continuation
from one-bar displacement.

This is not the rejected retest-high confirmation: it requires no pivot touch
or frozen retest bar, can occur anywhere in the 60-session setup lifecycle,
and pairs the entry with a repeated structural failure/re-entry rule.

## Frozen causal rule

For each PIT-eligible frozen VCP setup and completed daily bar:

1. the current and preceding two completed bars must have strictly increasing
   closes: `close[t-2] < close[t-1] < close[t]`;
2. the same bars must have strictly increasing lows:
   `low[t-2] < low[t-1] < low[t]`;
3. current close must be strictly above the frozen VCP pivot;
4. fill at the next session's open;
5. after entry, exit at the next open following the first completed close
   strictly below both preceding sessions' lows;
6. after exit, require a fresh qualifying three-bar staircase and permit at
   most three attempts per setup.

The unchanged frozen pattern stop and 60-session maximum hold can exit earlier.
All comparisons end at a completed close and every order executes no earlier
than the next open. Fixed Edge Rank sizing, initial capital, position/name/
sector/ADV limits, 8% risk cap, commission, slippage and cash treatment remain
unchanged. SPY is benchmark-only and can never be held.

## Density and multiplicity

Before return evaluation, count discovery signals after the exact lifecycle
but before portfolio rejection. Continue only for 80 through 500 signals. A
density failure records counts only and opens no return or later partition.

Count the three-bar window, rising-close condition, rising-low condition,
pivot confirmation, two-prior-low failure exit and three-attempt lifecycle as
six new multiplicity units, increasing declared evaluated trials from 393 to
399.

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
