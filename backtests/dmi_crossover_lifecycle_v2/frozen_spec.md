# Trial 363–367 — Wilder DMI Crossover Lifecycle

Status: **frozen before train, validation or best-available OOS return
evaluation** on 2026-08-01.

## Hypothesis

Prior momentum, path-efficiency, RS-line and volume rules measure endpoint
returns, smoothness, relative price or sponsorship. Wilder's Directional
Movement Index instead compares expansion in successive highs with expansion
in successive lows after normalising both by true range. A fresh `+DI` cross
above `-DI` while the stock is above its frozen VCP pivot may identify a new
directional impulse without requiring an arbitrary return threshold.

## Frozen causal rule

Compute 14-session Wilder-smoothed true range, positive directional movement
and negative directional movement from completed daily bars. Define `+DI` and
`-DI` as 100 times their respective Wilder smoothed directional movement
divided by Wilder smoothed true range.

For each PIT-eligible frozen VCP setup:

1. preceding `+DI` must be at or below preceding `-DI`;
2. current `+DI` must be strictly above current `-DI`;
3. current close must be strictly above the frozen VCP pivot;
4. fill at the next session's open;
5. exit at the next open after two consecutive later closes have `+DI < -DI`;
6. after an exit require a fresh crossover and permit at most three attempts
   per setup.

The existing pattern hard stop and 60-session maximum hold may exit earlier.
Every indicator uses data ending at the signal/exit close. The shared CSV
loader first scales OHLC by `Adj Close / Close` and outcome-free normalises
impossible high/low envelopes to include open and close. Detector and portfolio
use the identical transform. SPY is benchmark-only.

All portfolio sizing, initial capital, ten-position/name/sector/ADV limits,
8% maximum risk, commission, slippage and cash treatment remain fixed.

## Outcome-free density and multiplicity

The first prespecified variant additionally required ADX(14) >20 and rising.
It emitted only one discovery signal and was rejected from counts alone without
opening returns. One final family-level density check removed only that ADX
level/slope condition while retaining the DMI crossover, pivot and lifecycle;
it emitted 97 signals across 103 setups before portfolio rejections.

Count Wilder DMI(14), the directional crossover, pivot confirmation, the
two-close reverse-DMI exit and three-attempt lifecycle as five new multiplicity
units, increasing declared evaluated trials from 362 to 367. The rejected ADX
density definition is disclosed but not treated as a return-evaluated trial.

## Frozen 2006+ evidence boundary

- discovery/train: 2016-07-01 through 2018-06-30;
- embargo: 2018-07-01 through 2018-12-31;
- validation: 2019-01-01 through 2021-12-31;
- best-available frozen OOS: 2022-01-01 through 2026-03-31.

Every period has historical contamination and none may be described as
untouched. The final score must disclose unresolved survivorship and lack of a
genuine untouched OOS, applying the lowest rubric cap. No 2000–2005 data will
be searched or required.

## Sequential gates

Train requires all of:

- at least 60 completed trades;
- net CAGR at least 10%;
- Sharpe at least 0.75;
- profit factor above 1.20;
- MDD better than -15%;
- positive expectancy after removing the five largest trades.

Only a complete train pass opens the unchanged 2019–2021 validation rule.
Validation requires at least 60 trades, net CAGR at least 15%, and the same
quality gates. Only a complete validation pass may freeze a separate OOS run.
The OOS success bar remains net CAGR >=20% and at least 30 independent trades.

Every opened stage must report raw A/B/C/D, unavailable components, every hard
cap and the final capped score. A low score cap is acceptable; a failed CAGR,
trade-count, causality or fixed-portfolio condition is not.
