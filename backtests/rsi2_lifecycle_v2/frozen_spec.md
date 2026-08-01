# Trial 316–319 — RSI(2) Mean-Reversion Lifecycle Inside VCP

Status: **frozen before train/internal-holdout return evaluation** on 2026-08-01.

## Hypothesis

The fixed portfolio needs substantially more independent turnover than sparse
breakout filters can provide. Existing closing-low rules identify a new
five-session closing minimum and then use trend-follow-through exits. A
different, established mechanism is very short-horizon mean reversion inside
an otherwise valid VCP/uptrend: enter only after two-session downside intensity
is extreme and exit as soon as price recovers its short mean.

For every still-valid daily VCP setup:

- compute two-period RSI from closes through the signal bar;
- when RSI(2) is strictly below 10, enter at the next open;
- beginning with the entry-session close, exit next open after the first close
  strictly above causal SMA(5);
- otherwise exit at the open after five holding sessions;
- require five sessions between entries and allow at most three attempts per
  frozen setup.

The original pattern hard stop can exit earlier. A close below the frozen stop
invalidates later setup rows. No position is stacked: the engine exits before
processing same-day entries and rejects an entry while the name is held.

All PIT S&P 500 membership, adjusted OHLC, fixed Edge Rank sizing, cash,
ten-position/name/sector/ADV caps, 8% risk limit, commission, slippage, and
benchmark-only SPY controls remain fixed. Count RSI<10, SMA5 recovery, five-
session timeout, and maximum-three lifecycle as four multiplicity units,
raising 315 -> 319.

Sequential gate: first evaluate 2016-07-01..2018-06-30 signals with the existing
outcome buffer. Train requires at least 120 trades, CAGR at least 10%, Sharpe
at least 0.75, PF above 1.20, MDD better than -15%, and positive drop-top-five
expectancy. Failure keeps 2020–2021 sealed. If train passes, the unchanged rule
must produce at least 150 trades, CAGR at least 15%, and the same quality gates
on 2020–2021 before formal validation can be specified. Untouched OOS remains
sealed throughout.

