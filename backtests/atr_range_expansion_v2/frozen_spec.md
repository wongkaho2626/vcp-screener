# Trial 387–393 — ATR Range-Expansion Ignition Lifecycle

Status: **frozen before discovery return, validation or best-available OOS
evaluation** on 2026-08-01.

## Hypothesis

Prior volume, squeeze and directional-indicator families did not isolate VCP
continuation. A large bullish true-range expansion with the close near the
session high directly measures decisive price displacement from contraction,
without requiring volume confirmation. A short causal EMA exit then tests
whether that ignition persists.

## Frozen causal rule

For each PIT-eligible frozen VCP setup and completed daily bar:

1. compute current true range as the maximum of high-low, absolute high minus
   prior close, and absolute low minus prior close;
2. compute the arithmetic mean of true range over the preceding 20 completed
   sessions, excluding the current session;
3. require current true range >=1.5 times that prior-20 mean;
4. require close location `(close-low)/(high-low) >=0.75`, current close above
   prior close, and current close strictly above the frozen VCP pivot;
5. fill at the next session's open;
6. exit at the next open after two consecutive later completed closes strictly
   below their causal EMA(10);
7. after exit require a fresh qualifying range-expansion event and permit at
   most three attempts per setup.

EMA(10) uses the arithmetic mean of the first ten closes as seed and standard
alpha `2/(10+1)`. The unchanged frozen pattern stop and 60-session maximum hold
can exit earlier. Fixed Edge Rank sizing, initial capital, position/name/sector/
ADV limits, 8% risk cap, commission, slippage and cash treatment remain
unchanged. SPY is benchmark-only and can never be held.

## Density and multiplicity

Before return evaluation, count discovery signals after the exact rule but
before portfolio rejection. Continue only for 80 through 500 signals. A density
failure records counts only and opens no return or later evidence partition.

Count ATR lookback 20, expansion multiple 1.5, close-location threshold 0.75,
positive-close/pivot confirmation, EMA10 exit, two-close exit confirmation and
three-attempt lifecycle as seven new multiplicity units, increasing declared
evaluated trials from 386 to 393.

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
