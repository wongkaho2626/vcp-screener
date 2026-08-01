# Trial 448–454 — Gap-Adjusted Intraday Follow-Through Lifecycle

Status: **frozen before discovery density, return, validation or best-available
OOS evaluation** on 2026-08-01.

## Hypothesis and prior evidence

The earlier breakout-gap conditioning experiment found that large entry-day
gap-ups were adverse rather than positive, but used a legacy gross trade log
with mixed fills. ATR expansion, gap recovery and total-return momentum also
failed. This new rule does not classify a single entry-day gap. It decomposes
each completed daily return into overnight and regular-session log returns and
asks whether recent gains were earned during regular trading rather than
arriving through gaps.

Positive rolling intraday return that exceeds rolling overnight return may
identify continuous demand and avoid chasing overnight repricing. This
post-gap-null rationale and the broad negative momentum prior are disclosed.
There is one fixed window and no gap-size, lookback or comparison scan.

## Frozen causal rule

For the most recent 10 completed sessions ending on the current session,
calculate:

- regular-session sum = `sum(log(close_t / open_t))`;
- overnight sum = `sum(log(open_t / close_(t-1)))`.

All opens and closes use the shared adjusted-OHLC transform already frozen for
detection and portfolio execution. Each 10-session calculation therefore needs
the preceding close but ends on the current completed close.

For each PIT-eligible frozen VCP setup:

1. enter when regular-session sum is strictly positive, strictly greater than
   overnight sum, and current close is strictly above the frozen pivot;
2. fill at the next session's open;
3. define follow-through failure when regular-session sum is at or below zero;
4. exit at the next open after two consecutive later completed sessions in
   follow-through failure;
5. after exit require a later qualifying state and permit at most three
   attempts per setup.

The unchanged frozen pattern stop and 60-session maximum hold can exit earlier.
Fixed Edge Rank sizing, initial capital, position/name/sector/ADV limits, 8%
risk cap, commission, slippage and cash treatment remain unchanged. SPY is
benchmark-only and can never be held.

## Density and multiplicity

Before return evaluation, count discovery signals after the exact lifecycle
but before portfolio rejection. Continue only for 80 through 500 signals. A
density failure records counts only and opens no return or later partition.

Count the 10-session window, log-return decomposition, positive intraday
condition, intraday-over-overnight comparison, pivot confirmation, two-close
failure exit and three-attempt lifecycle as seven new multiplicity units,
increasing declared evaluated trials from 447 to 454.

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
