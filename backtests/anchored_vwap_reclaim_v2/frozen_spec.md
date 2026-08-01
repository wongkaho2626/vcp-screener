# Trial 352–357 — Detection-Anchored VWAP Reclaim Lifecycle

Status: **frozen before train or internal-holdout return evaluation** on
2026-08-01.

## Hypothesis

A VCP detection date is a causal, setup-specific anchor for the period in which
institutional sponsorship should become visible. A stock that first loses and
then reclaims the volume-weighted cost basis accumulated since that date may
offer better timing than an unqualified pivot breakout. Requiring the frozen
pivot at entry keeps the signal aligned with VCP structure, while two closes
below anchored VWAP avoid exiting on a one-day undercut.

## Frozen causal rule

For each point-in-time eligible VCP setup, anchor an expanding VWAP on its
frozen `as_of_date`. For every session from the anchor through the current
close, calculate typical price as `(high + low + close) / 3` and calculate:

`AVWAP = cumulative(typical_price * volume) / cumulative(volume)`.

Only observations available at the current close enter either cumulative sum.
If cumulative volume is non-positive, the AVWAP state is unavailable.

1. the preceding close must be at or below its causal detection-anchored VWAP;
2. the current close must be strictly above both its causal anchored VWAP and
   the setup's frozen VCP pivot;
3. fill the entry at the next session's open;
4. exit at the next open only after two consecutive later closes strictly below
   their causal anchored VWAP;
5. after an exit, require a fresh below-to-above anchored-VWAP reclaim and allow
   at most three attempts per frozen setup.

The existing frozen pattern hard stop and 60-session maximum hold can exit
earlier. A setup is invalid after a close below its frozen pattern stop. All
OHLCV, AVWAP and pivot inputs end at the signal or exit close; every order fills
no earlier than the next open. No future bar, outcome or SPY signal is used.
SPY remains benchmark-only.

PIT S&P 500 membership, adjusted OHLC parity, fixed Edge Rank sizing, initial
capital, ten-position/name/sector/ADV constraints, 8% maximum risk, commission,
slippage, cash treatment and all other portfolio controls remain unchanged.

One outcome-free density audit inspected counts only: 4,165 eligible train
setup-day rows across 103 setups produced 112 entry signals before portfolio
rejections. No trade return or future outcome was opened.

Count the detection-date anchor, typical-price/volume cumulative AVWAP, reclaim
crossover, frozen-pivot confirmation, two-close AVWAP exit and three-attempt
lifecycle as six new multiplicity units, raising the declared total from 351 to
357.

## Sequential gate

Evaluate 2016-07-01 through 2018-06-30 train first. Train requires all of:

- at least 60 completed trades;
- net CAGR at least 10%;
- Sharpe at least 0.75;
- profit factor above 1.20;
- MDD better than -15%;
- positive expectancy after removing the five largest trades.

Only a full train pass permits the unchanged rule to access the already-used
2020–2021 internal discovery holdout. That holdout requires at least 60 trades,
net CAGR at least 15%, and the same quality gates before any separate formal
validation specification may be frozen. Formal validation and untouched OOS
remain sealed otherwise.

Every result must show the reduced-denominator A/B/C/D Backtest Score, its raw
normalized value, the unresolved-survivorship cap of 20, the no-formal-OOS/WFA
cap of 55, and the final score after the lower applicable cap. There is no
minimum score threshold; the cap is accepted when transparently disclosed.
