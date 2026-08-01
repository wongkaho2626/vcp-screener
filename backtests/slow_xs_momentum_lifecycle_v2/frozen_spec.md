# Trial 412–417 — Slow Cross-Sectional Momentum VCP Lifecycle

Status: **frozen before discovery return, validation or best-available OOS
evaluation** on 2026-08-01.

## Hypothesis and prior evidence

PIT-clean 12–1 cross-sectional momentum was weakly positive in the repository's
standalone monthly factor experiment, while Trial 320–323's absolute 12–1 plus
five-day crossover lost money and Trial 328–333's active-VCP 5d/20d rank was
positive only before removing five winners. None tested whether the canonical
slow 12–1 factor can rank simultaneous active VCP opportunities.

The hypothesis is that a top-quintile 12–1 rank among the contemporaneous
active-VCP cohort identifies persistent relative leaders, while falling to the
cohort median marks loss of that scarce portfolio-slot advantage. This is one
fixed horizon/threshold pair, not a rank or lookback scan.

## Frozen causal rule

For every completed trading date, keep at most one active setup row per symbol:
the most recent PIT-eligible detection, breaking an exact-date tie by higher
frozen Edge Rank. Using only stock closes available on that date:

1. calculate `momentum_12_1 = close[t-21] / close[t-252] - 1`;
2. percentile-rank valid scores among that date's active-VCP cohort; average
   ties and assign 0.5 to a one-symbol cohort;
3. enter the first available state at rank >=0.80 while current close is
   strictly above the setup's frozen pivot; fill at the next open;
4. exit at the next open after the first later completed state with rank <=0.50;
5. after exit require rank >=0.80 again and permit at most three attempts per
   frozen setup.

The score deliberately excludes the most recent 21 sessions. No future cohort,
future return, SPY value or non-member security enters the signal. The unchanged
frozen pattern stop and 60-session maximum hold can exit earlier. Fixed Edge
Rank sizing, initial capital, position/name/sector/ADV limits, 8% risk cap,
commission, slippage and cash treatment remain unchanged. SPY is benchmark-only
and can never be held.

## Density and multiplicity

Before return evaluation, count discovery signals after the exact lifecycle
but before portfolio rejection. Continue only for 80 through 500 signals. A
density failure records counts only and opens no return or later partition.

Count the 252-session lookback, 21-session skip, active-cohort percentile rank,
0.80 entry, 0.50 exit and three-attempt lifecycle as six new multiplicity
units, increasing declared evaluated trials from 411 to 417.

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
