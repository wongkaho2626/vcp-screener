# Trial 381–386 — Donchian 55/20 Price-Channel Lifecycle

Status: **frozen before discovery return, validation or best-available OOS
evaluation** on 2026-08-01.

## Hypothesis

The rejected DMI, Parabolic SAR and MACD families define continuation through
indicator state. A canonical Donchian channel instead asks whether the VCP has
resolved into an objective multi-month closing high, then stays invested until
an objective intermediate closing low. This price-structure rule may suppress
false pivot breaks while allowing genuine trends to compound.

## Frozen causal rule

For each PIT-eligible frozen VCP setup and each completed daily bar:

1. calculate the highest close of the preceding 55 completed sessions,
   excluding the current close;
2. a bullish signal requires current close strictly above that prior 55-session
   high and strictly above the frozen VCP pivot;
3. fill at the next session's open;
4. after entry, exit at the next open following the first completed close
   strictly below the lowest close of its preceding 20 completed sessions;
5. after exit, require a fresh 55-session closing high and permit at most three
   attempts per setup.

The unchanged frozen pattern stop and 60-session maximum hold can exit earlier.
All rolling windows exclude the current bar; all orders therefore use only
completed information and execute no earlier than the next open. Fixed Edge
Rank sizing, initial capital, position/name/sector/ADV limits, 8% risk cap,
commission, slippage and cash treatment remain unchanged. SPY is benchmark-only
and can never be held.

## Density and multiplicity

Before any return evaluation, count discovery signals after the exact rule but
before portfolio rejection. Continue only for 80 through 500 signals. A density
failure is recorded without opening returns or any later partition. The limits
are identical to the prior MACD audit and are frozen before the count.

Count the 55-session entry channel, 20-session exit channel, strict closing-high
definition, frozen-pivot confirmation, one-close channel exit and three-attempt
lifecycle as six new multiplicity units, increasing declared evaluated trials
from 380 to 386.

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
