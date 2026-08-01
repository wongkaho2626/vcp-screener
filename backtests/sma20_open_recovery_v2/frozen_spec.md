# Trial 324–327 — SMA20 Opening-Limit / Gap-Recovery Lifecycle

Status: **frozen before train or internal-holdout return evaluation** on
2026-08-01.

## Hypothesis

The original research found a robust execution improvement from waiting for an
MA20 pullback, but the ordinary one-entry VCP portfolio remained underexposed.
RSI(2) mean reversion entered falling closes and failed. This rule tests a
different, executable event: after a VCP closes above its causal SMA20, place a
one-session limit at that SMA20. A next-session opening gap through the limit
provides a price concession known at the open; the position exits only after a
later close repairs the entire overnight gap.

For each still-valid point-in-time VCP setup:

1. after close `t`, require `close[t] > SMA20[t] > frozen pattern stop`;
2. place a one-session buy limit at `SMA20[t]` for session `t+1`;
3. fill only if `open[t+1] <= SMA20[t]` and `open[t+1] > pattern stop`, at that
   observed open plus unchanged costs;
4. if the entry session later touches the unchanged initial stop, record a
   same-session stop exit with both sides' costs; this prevents daily-bar
   ordering optimism;
5. otherwise, after the first later close at or above the pre-gap `close[t]`,
   exit at the following open;
6. if no recovery occurs, exit at the open after ten holding sessions;
7. allow a new independent opening-limit event only after the scheduled prior
   exit, with at most three attempts per frozen setup.

All entry conditions except the next open are known when the resting order is
placed. The open is an execution condition, not a future-labelled predictor.
Recovery and timeout exits are close-confirmed and execute at the next open.
SPY is not used by the signal and remains benchmark-only.

PIT S&P 500 membership, adjusted OHLC parity, fixed Edge Rank sizing, initial
cash, ten-position/name/sector/ADV constraints, 8% maximum risk, hard stop,
commission and slippage remain unchanged. Count the prior-SMA20 opening limit,
full-gap recovery target, ten-session timeout and three-attempt lifecycle as
four multiplicity units, raising 323 to 327.

## Sequential gate

Evaluate 2016-07-01 through 2018-06-30 train first. Train requires at least 60
completed trades, net CAGR at least 10%, Sharpe at least 0.75, profit factor
above 1.20, MDD better than -15%, and positive expectancy after removing the
five largest trades.

Only a full train pass permits the unchanged rule to access the already-used
2020–2021 internal discovery holdout. That holdout requires at least 60 trades,
net CAGR at least 15%, and the same quality gates before a separate formal
validation specification may be frozen. Formal validation and untouched OOS
remain sealed otherwise.
