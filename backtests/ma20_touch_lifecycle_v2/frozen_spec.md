# Trial 400–405 — Repeated MA20 Touch-and-Hold Lifecycle

Status: **frozen before discovery return, validation or best-available OOS
evaluation** on 2026-08-01.

## Hypothesis and prior evidence

The repository's only repeatable execution-layer improvement is the causal
MA20 touch-and-hold after a VCP breakout. On 2016–2026 PIT data it improved
paired trade outcomes by 0.98 percentage points (t=2.73), but absolute excess
remained negative, the 2006–2015 PIT OOS replication failed, and the effect
faded after 2021. This prior is disclosed rather than treated as fresh alpha.

The new hypothesis is narrower: recycling only fresh MA20 touch-and-hold events
after a confirmed pivot breakout, with an MA20 failure exit, may turn the known
entry-price improvement into sufficient portfolio exposure without changing
sizing. The rule deliberately removes the old 15-session one-shot expiry to
test a repeated lifecycle; this is a new family and counts toward multiplicity.

## Frozen causal rule

For each PIT-eligible frozen VCP setup:

1. eligibility begins only after a completed close crosses from below to at or
   above the frozen pivot;
2. calculate SMA20 including the current completed close;
3. a raw touch-and-hold state is `low <= SMA20 <= close` while eligible and
   above the frozen pattern stop;
4. enter only on a fresh state transition from no touch-and-hold on the prior
   session to touch-and-hold now; fill at the next session's open;
5. exit at the next open after two consecutive later completed closes strictly
   below their causal SMA20;
6. after exit require another fresh touch-and-hold transition and permit at
   most three attempts per setup.

The unchanged frozen pattern stop and 60-session maximum hold can exit earlier.
All signal/exit information ends at the completed close. Fixed Edge Rank
sizing, initial capital, position/name/sector/ADV limits, 8% risk cap,
commission, slippage and cash treatment remain unchanged. SPY is benchmark-only
and can never be held.

## Density and multiplicity

Before return evaluation, count discovery signals after the exact lifecycle
but before portfolio rejection. Continue only for 80 through 500 signals. A
density failure records counts only and opens no return or later partition.

Count the pivot-crossover eligibility state, SMA20, touch-and-hold condition,
fresh-transition requirement, two-close SMA20 exit and three-attempt lifecycle
as six new multiplicity units, increasing declared evaluated trials from 399
to 405.

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
