# Trial 374–380 — MACD Signal-Line Crossover Lifecycle

Status: **frozen before discovery return, validation or best-available OOS
evaluation** on 2026-08-01.

## Hypothesis

The failed DMI and Parabolic SAR families measure directional range expansion
and price-relative trend state. Standard MACD instead measures the acceleration
of two causal exponential close trends. A fresh bullish MACD/signal-line
crossover in positive territory, while price is above the already-frozen VCP
pivot, may isolate accelerating continuation after contraction without using
future outcomes.

## Frozen causal rule

Compute close-only EMA(12), EMA(26), MACD = EMA(12) - EMA(26), and a 9-session
EMA of the available MACD values. Each EMA uses its arithmetic mean as its
initial seed and then the standard alpha `2 / (period + 1)`. All calculations
end at the completed close.

For each PIT-eligible frozen VCP setup:

1. prior MACD must be at or below its prior signal line;
2. current MACD must be strictly above its signal line and zero;
3. current close must be strictly above the frozen VCP pivot;
4. fill at the next session's open;
5. exit at the next open after two consecutive later completed closes whose
   MACD is below its signal line;
6. after exit, require a fresh bullish crossover and allow at most three
   attempts per setup.

The unchanged frozen pattern stop and 60-session maximum hold can exit earlier.
Fixed Edge Rank sizing, initial capital, position/name/sector/ADV limits, 8%
risk cap, commission, slippage and cash treatment remain unchanged. SPY is
benchmark-only and can never be held.

## Density and multiplicity

Before any return evaluation, count discovery signals after the exact rule but
before portfolio rejection. Continue only for 80 through 500 signals. Fewer
than 80 cannot plausibly provide the required 60 train trades after normal
portfolio rejection; more than 500 is an unintended high-turnover regime. A
density failure is recorded without opening returns or later partitions.

Count EMA(12), EMA(26), signal EMA(9), positive-territory filter, pivot
confirmation, two-close exit and three-attempt lifecycle as seven new
multiplicity units, increasing declared evaluated trials from 373 to 380.

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
