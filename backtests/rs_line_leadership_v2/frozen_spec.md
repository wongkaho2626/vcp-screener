# Trial 340–344 — Relative-Strength-Line Leadership Lifecycle

Status: **frozen before train or internal-holdout return evaluation** on
2026-08-01.

## Hypothesis

The detector and Edge Rank use relative strength at setup formation, but no
prior experiment timed entries from a causal daily stock/SPY relative-strength
line. A VCP whose RS line reaches a three-month high while price confirms above
the pivot may represent stock-specific leadership rather than market beta. A
joint RS-line and price-trend failure should distinguish an ordinary pause from
a genuine loss of leadership.

SPY is used only as the benchmark denominator. It can never be submitted as an
order, held, or used as a fallback asset.

## Frozen causal rule

For each stock bar, align SPY to the latest benchmark session whose date is no
later than the stock date and define `RS = stock close / aligned SPY close`.
For every point-in-time eligible daily VCP setup:

1. require the current RS value to be strictly above every prior RS value in
   the preceding 63 stock sessions;
2. additionally require the current stock close to be strictly above the
   frozen VCP pivot and its causal stock SMA20;
3. fill at the next session's open;
4. exit at the next open only after a later close is simultaneously below the
   causal 20-session SMA of the RS line and below the causal stock SMA20;
5. after a scheduled exit, permit a later independent 63-session RS-line high,
   with at most three attempts per frozen setup.

The existing pattern hard stop and 60-session maximum hold can exit earlier.
A setup is invalid after a close below its frozen pattern stop. All stock and
benchmark observations end at the signal/exit close. The date-alignment rule
forbids a future SPY observation, and every fill is delayed to the next open.

PIT S&P 500 membership, adjusted OHLC parity, fixed Edge Rank sizing, initial
capital, ten-position/name/sector/ADV constraints, 8% maximum risk, commission,
slippage, cash treatment and every other portfolio control remain unchanged.

The outcome-free density check inspected signal counts only: this fixed rule
emitted 80 train signals before portfolio rejections. No trade return or future
outcome was opened by that check.

Count the 63-session RS high, joint pivot/stock-SMA20 entry confirmation,
20-session RS-SMA exit, joint stock-SMA20 exit confirmation, and three-attempt
lifecycle as five new multiplicity units, raising the declared total from 339
to 344.

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
