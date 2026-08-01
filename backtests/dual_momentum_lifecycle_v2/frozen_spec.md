# Trial 320–323 — Dual-Momentum VCP Lifecycle

Status: **frozen before train or internal-holdout return evaluation** on
2026-08-01.

## Hypothesis

The daily entry/exit oracle shows that the remaining opportunity requires joint
within-setup timing and exit selection. Prior lifecycle attempts used score
hysteresis, closing lows, or RSI(2) mean reversion. This rule instead tests a
standard trend-continuation mechanism: a still-valid VCP with positive 12–1
absolute momentum is entered when five-session momentum crosses from
non-positive to positive, then held only while its medium-term trend remains
intact.

For each point-in-time eligible daily VCP setup:

1. compute absolute 12–1 momentum as `close[t-21] / close[t-252] - 1`;
2. compute five-session momentum as `close[t] / close[t-5] - 1`;
3. signal only when 12–1 momentum is strictly positive and five-session
   momentum crosses from `<=0` on `t-1` to `>0` on `t`;
4. enter at the next session's open;
5. exit at the next open after the first close strictly below causal SMA(20);
6. after that scheduled exit, allow a later fresh five-session crossing, with
   at most three attempts per frozen setup.

The existing pattern hard stop and 60-session maximum hold can exit earlier.
The setup is invalid after a close below its frozen stop. No SPY value is used
by the signal; SPY remains benchmark-only. All indicator inputs end at the
signal or exit close, and every fill is delayed until the next open.

PIT S&P 500 membership, adjusted OHLC parity, fixed Edge Rank sizing, initial
cash, ten-position/name/sector/ADV constraints, 8% maximum risk, commissions,
slippage, and all other risk controls remain unchanged. Count the 12–1
lookback, five-session crossing, SMA20 exit, and three-attempt lifecycle as
four new multiplicity units, raising 319 to 323.

## Sequential gate

Evaluate 2016-07-01 through 2018-06-30 train first, with the existing warm-up
and outcome buffer. Train requires at least 60 completed trades, net CAGR at
least 10%, Sharpe at least 0.75, profit factor above 1.20, MDD better than
-15%, and positive expectancy after removing the five largest trades.

Only a full train pass permits the unchanged rule to access the already-used
2020–2021 internal discovery holdout. That holdout requires at least 60 trades,
net CAGR at least 15%, and the same quality gates before a separate formal
validation specification may be frozen. Formal validation and untouched OOS
remain sealed otherwise.
