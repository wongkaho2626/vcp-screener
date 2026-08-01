# Trial 432–440 — Causal Ichimoku Range-Midpoint Equilibrium Lifecycle

Status: **frozen before discovery density, return, validation or best-available
OOS evaluation** on 2026-08-01.

## Hypothesis and prior evidence

Moving averages, price channels, DMI, MACD, PSAR, OLS trend quality and Aroon
extreme recency have failed. Ichimoku's canonical 9/26/52-session construction
is mechanically different because it compares multi-horizon *high-low range
midpoints*. A close above both current range-midpoint spans, with the fast
midpoint above the base midpoint and the frozen VCP pivot, may identify a
balanced continuation state that is not captured by return magnitude or a
single extreme.

The extensive negative price-trend prior is disclosed. No visual/forward cloud
displacement or Chikou span is used: every value ends on the current completed
session. This is one fixed canonical parameterisation with no threshold or
lookback scan.

## Frozen causal rule

On every completed session calculate:

- Tenkan = midpoint of the highest high and lowest low over the last 9
  sessions;
- Kijun = midpoint of the highest high and lowest low over the last 26
  sessions;
- current Span A = midpoint of current Tenkan and current Kijun;
- current Span B = midpoint of the highest high and lowest low over the last
  52 sessions.

For each PIT-eligible frozen VCP setup:

1. enter on the first completed close where Tenkan is strictly above Kijun and
   close is strictly above the frozen pivot, current Span A and current Span B;
2. fill at the next session's open;
3. define equilibrium failure when Tenkan is strictly below Kijun;
4. exit at the next open after two consecutive later completed sessions in
   equilibrium failure;
5. after exit require a later qualifying state and permit at most three
   attempts per setup.

The unchanged frozen pattern stop and 60-session maximum hold can exit earlier.
All rolling windows end at the signal/exit close. Fixed Edge Rank sizing,
initial capital, position/name/sector/ADV limits, 8% risk cap, commission,
slippage and cash treatment remain unchanged. SPY is benchmark-only and can
never be held.

## Density and multiplicity

Before return evaluation, count discovery signals after the exact lifecycle
but before portfolio rejection. Continue only for 80 through 500 signals. A
density failure records counts only and opens no return or later partition.

Count the 9-, 26- and 52-session windows, fast/base ordering, dual current-span
confirmation, frozen-pivot confirmation, reverse-order failure, two-close exit
and three-attempt lifecycle as nine new multiplicity units, increasing declared
evaluated trials from 431 to 440.

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
