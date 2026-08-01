# Trial 328–333 — Cross-Sectional VCP Leadership Lifecycle

Status: **frozen before train or internal-holdout return evaluation** on
2026-08-01.

## Hypothesis

The daily VCP opportunity set is dense enough to contain several simultaneously
active names, but prior rules evaluated each setup mostly in isolation. The
forward-timing ridge used absolute return features, while the failed dual-
momentum lifecycle used absolute 12–1 and five-session momentum. Neither tested
whether a still-valid VCP is gaining leadership relative to the other VCPs that
could consume the same portfolio slots on that date.

The declared hypothesis is that persistent winners should rank well across both
short and intermediate horizons inside the contemporaneous active-VCP cohort,
and should be sold when that relative leadership and the local trend both fail.

## Frozen causal rule

For every date, keep at most one active setup row per symbol: the most recent
point-in-time detection, breaking an exact-date tie by the higher frozen Edge
Rank. Using only closes available on that date:

1. compute each active symbol's 5-session and 20-session close return;
2. percentile-rank each return cross-sectionally among that day's eligible
   active VCP symbols; a one-symbol cohort receives rank 0.5;
3. define leadership as the equal-weighted mean of the two percentile ranks;
4. require `close > causal SMA20` and enter when leadership crosses from below
   0.70 to at least 0.70, filling at the next session's open;
5. exit at the next open after leadership is at or below 0.40 **and** the close
   is below causal SMA20;
6. after an exit condition, require a later fresh crossing from below 0.70 and
   allow at most three attempts per frozen setup.

The existing pattern hard stop and 60-session maximum hold can exit earlier.
A setup is invalid after a close below its frozen pattern stop. No future row,
future cohort, SPY value, or future return is used by the signal. Entry and exit
conditions are close-confirmed and execute no earlier than the next open.

PIT S&P 500 membership, adjusted OHLC parity, fixed Edge Rank sizing, initial
capital, ten-position/name/sector/ADV constraints, 8% maximum risk, commission,
slippage, cash treatment, and all other portfolio controls remain unchanged.
SPY is benchmark-only and cannot be held.

Count the 5-session horizon, 20-session horizon, equal-weight rank combination,
0.70 entry threshold, joint 0.40/SMA20 exit, and three-attempt lifecycle as six
new multiplicity units, raising the declared total from 327 to 333.

## Sequential gate

Evaluate 2016-07-01 through 2018-06-30 train first, retaining only signals and
fills with PIT membership. Train requires all of:

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
