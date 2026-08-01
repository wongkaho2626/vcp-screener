# Trial 455–466 — AVWAP Reclaim with Delayed Five-Day-High Exit

Status: **frozen before this specification's discovery density, return,
validation or best-available OOS evaluation** on 2026-08-01.

## Hypothesis provenance and limitations

This is explicitly train-oracle-generated and is not an independent hypothesis.
The non-deployable residual audit inspected six fixed causal states on the close
before 90 perfect-foresight exits. A fresh five-day closing high covered 84.4%
overall, 84.6%/84.2% in the two train halves and 84.7% after removing the five
largest oracle returns. Weakness and giveback states had very low coverage.

The entry is also selected post hoc: detection-anchored AVWAP reclaim had the
strongest recent untrimmed PF (1.386) but failed its train gate and drop-top-five
test. Pairing that institutional-cost-basis entry with a delayed sell-into-
strength exit may realize gains before the prior AVWAP-failure exit gives them
back. This selection and all oracle proxy reads count toward multiplicity.

## Frozen causal rule

Entry is unchanged from Trial 352–357:

1. anchor causal typical-price/volume VWAP on the frozen setup detection date;
2. after a completed close at or below its then-current AVWAP, require a later
   completed close strictly above current AVWAP and the frozen pivot;
3. fill at the next session's open.

Exit:

1. preserve the unchanged resting hard stop and 60-session maximum hold;
2. do not permit the new exit until 10 completed holding sessions have elapsed;
3. thereafter, the first completed close strictly above each of the preceding
   four completed closes is a fresh five-day closing high;
4. exit the full position at the next session's open;
5. after exit, require a later fresh below-to-above AVWAP reclaim and permit at
   most three attempts per setup.

No profit threshold, partial sale, trailing distance, alternative high window
or arming period is scanned. Fixed Edge Rank sizing, initial capital,
position/name/sector/ADV limits, 8% risk cap, commission, slippage and cash
treatment remain unchanged. SPY is benchmark-only and can never be held.

## Density and multiplicity

Before return evaluation, count discovery signals after the exact lifecycle
but before portfolio rejection. Continue only for 80 through 500 signals. A
density failure records counts only and opens no return or later partition.

Count six inspected oracle proxies, post-hoc AVWAP entry-family selection, the
five-day window, strict new-high comparison, 10-session arm, next-open strength
exit and three-attempt lifecycle as twelve new multiplicity units, increasing
declared evaluated trials from 454 to 466.

## Frozen chronology and gates

- discovery/train: 2016-07-01 through 2018-06-30;
- embargo: 2018-07-01 through 2018-12-31;
- validation: 2019-01-01 through 2021-12-31;
- capped best-available OOS: 2022-01-01 through 2026-03-31.

Train requires >=60 trades, CAGR >=10%, Sharpe >=0.75, PF >1.20, MDD better
than -15%, and positive drop-top-five expectancy. Because the mechanism is
train-oracle-generated, even a train pass is only permission to open the frozen
validation once; it is never evidence by itself. Validation requires >=60
trades, CAGR >=15%, Sharpe >=0.75, PF >1.20, MDD better than -15% and positive
drop-top-five expectancy. Only a complete validation pass may open the unchanged
OOS; OOS success requires >=20% net CAGR and >=30 independent trades.

All periods are contaminated by prior research and must not be described as
untouched. Reports must show raw A/B/C/D, every applicable survivorship/OOS cap
and final score. Missing 2000–2005 data is out of scope.
