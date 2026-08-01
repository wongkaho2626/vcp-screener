# Trial 345–351 — Volatility Squeeze-Release VCP Lifecycle

Status: **frozen before train or internal-holdout return evaluation** on
2026-08-01.

## Hypothesis

VCP is explicitly a volatility-contraction pattern, yet prior timing rules did
not require a measurable transition from unusually compressed volatility to
directional expansion. A breakout attempted while bandwidth is still shrinking
may lack sponsorship; waiting for bandwidth to turn upward after a historical
squeeze may better identify the start of the expansion phase.

## Frozen causal rule

For each close, compute a causal 20-session Bollinger bandwidth as
`4 * population_std(close, 20) / SMA20`. The constant four represents the full
width of +/-2 standard-deviation bands but only the relative width is used.

For every point-in-time eligible daily VCP setup:

1. the preceding close's bandwidth must be at or below the 20th percentile of
   the 126 bandwidth observations ending on that preceding close;
2. current bandwidth must be strictly greater than preceding bandwidth;
3. current close must be strictly above both the preceding close and the
   frozen VCP pivot;
4. fill at the next session's open;
5. exit at the next open after the first later close strictly below causal
   SMA20;
6. after an exit, require a new independently observed squeeze-release event
   and allow at most three attempts per frozen setup.

The existing pattern hard stop and 60-session maximum hold can exit earlier.
A setup is invalid after a close below its frozen pattern stop. All bandwidth,
percentile, pivot and SMA values end at the signal/exit close; every order fills
no earlier than the next open. No future bar, outcome or SPY signal is used.
SPY remains benchmark-only.

PIT S&P 500 membership, adjusted OHLC parity, fixed Edge Rank sizing, initial
capital, ten-position/name/sector/ADV constraints, 8% maximum risk, commission,
slippage, cash treatment and all other portfolio controls remain unchanged.

Two outcome-free density checks inspected counts only. The stricter +2-sigma
upper-band breakout emitted 31 train signals and was rejected before becoming
a trial because it could not meet the 60-trade train gate. The frozen
bandwidth-expansion/up-close rule emitted 85 train signals before portfolio
rejections. No trade return or future outcome was opened in either check.

Count the 20-session bandwidth, 126-session reference window, 20th-percentile
squeeze, bandwidth-expansion/up-close release, pivot confirmation, SMA20 exit
and three-attempt lifecycle as seven new multiplicity units, raising the
declared total from 344 to 351.

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
