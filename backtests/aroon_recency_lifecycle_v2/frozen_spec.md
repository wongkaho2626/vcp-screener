# Trial 425–431 — Aroon Extreme-Recency Lifecycle

Status: **frozen before discovery return, validation or best-available OOS
evaluation** on 2026-08-01.

## Hypothesis and prior evidence

Magnitude-based momentum, DMI, Donchian, MACD, PSAR, path efficiency and
log-price regression quality have failed. Aroon measures a different state:
the *recency* of the most recent high relative to the most recent low, without
using the size or smoothness of the intervening move. A recent high and stale
low above a frozen VCP pivot may identify an early continuation phase; reversal
of that recency ordering supplies a causal lifecycle exit.

This rule does not require a fresh channel high, so it is not a Donchian
retest. It does not use directional-movement magnitude, return magnitude,
volume or fitted trend quality. The broad negative trend-family prior is
disclosed. This is one fixed parameterisation with no threshold scan.

## Frozen causal rule

Using the most recent 25 completed sessions including the current session:

- `Aroon Up = 100 * (25 - sessions_since_most_recent_high) / 25`;
- `Aroon Down = 100 * (25 - sessions_since_most_recent_low) / 25`.

Tied extremes use their most recent occurrence. For each PIT-eligible frozen
VCP setup:

1. enter on the first completed close where Aroon Up is at least 70, Aroon
   Down is at most 50, Aroon Up is strictly greater than Aroon Down, and close
   is strictly above the frozen pivot;
2. fill at the next session's open;
3. define recency failure when Aroon Up is strictly below Aroon Down;
4. exit at the next open after two consecutive later completed sessions in
   recency failure;
5. after exit require a later qualifying state and permit at most three
   attempts per setup.

The unchanged frozen pattern stop and 60-session maximum hold can exit earlier.
All extrema end at the signal/exit close. Fixed Edge Rank sizing, initial
capital, position/name/sector/ADV limits, 8% risk cap, commission, slippage and
cash treatment remain unchanged. SPY is benchmark-only and can never be held.

## Density and multiplicity

Before return evaluation, count discovery signals after the exact lifecycle
but before portfolio rejection. Continue only for 80 through 500 signals. A
density failure records counts only and opens no return or later partition.

Count the 25-session window, recent-high threshold, stale-low threshold,
frozen-pivot confirmation, reverse-recency failure, two-close exit and
three-attempt lifecycle as seven new multiplicity units, increasing declared
evaluated trials from 424 to 431.

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
