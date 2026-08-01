# Trial 368–373 — Parabolic SAR Flip Lifecycle

Status: **frozen before train, validation or best-available OOS return
evaluation** on 2026-08-01.

## Hypothesis

Fixed-window momentum, path efficiency, moving-average, volume and DMI rules
have not found a durable VCP continuation edge. Parabolic SAR adapts its
distance to both trend duration and each newly observed extreme. A completed
close that flips from below to above a standard PSAR while also reclaiming the
frozen VCP pivot may isolate trend re-acceleration without changing sizing or
using future outcomes.

## Frozen causal rule

Calculate standard daily Parabolic SAR with acceleration step 0.02 and maximum
0.20. Initial direction uses only the first two available closes. Each later
SAR update uses completed current/prior OHLC, the current extreme point and
acceleration factor; it is constrained by the preceding two lows in an uptrend
or highs in a downtrend. The shared loader first applies the outcome-free
adjusted-OHLC envelope repair documented in the 2006+ inventory.

For each PIT-eligible frozen VCP setup:

1. preceding close must be at or below preceding PSAR;
2. current close must be strictly above current PSAR and the frozen pivot;
3. fill at the next session's open;
4. exit at the next open after two consecutive later closes below their PSAR;
5. after an exit require a fresh below-to-above close crossover and permit at
   most three attempts per setup.

The unchanged frozen pattern stop and 60-session maximum hold can exit earlier.
All signal and exit values end at the completed close. Fixed Edge Rank sizing,
initial capital, position/name/sector/ADV limits, 8% risk cap, commission,
slippage and cash treatment remain unchanged. SPY is benchmark-only.

## Density and multiplicity

One outcome-free audit counted 4,165 discovery setup-day rows, 103 setups and
129 signals before portfolio rejections. No return or later partition was
opened.

Count the 0.02 acceleration step, 0.20 maximum, close crossover, pivot
confirmation, two-close PSAR exit and three-attempt lifecycle as six new
multiplicity units, increasing declared evaluated trials from 367 to 373.

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
