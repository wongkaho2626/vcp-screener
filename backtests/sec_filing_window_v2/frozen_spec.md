# Trial 303–304 — Fresh SEC Dual-Growth Filing Window

Status: **frozen before internal-holdout evaluation** on 2026-08-01.

## Train-only hypothesis

The SEC feature audit used only the 2016-07-01..2018-06-30 fit labels. Among
dual-growth setups, the first active VCP state no more than 30 days after the
filing had 13 setup-level observations, mean hard-stop-aware forward-20 net
return +4.54%, median +4.53%, and 12/13 positive. The corresponding first state
within 120 days averaged only +0.92%. This suggests the orthogonal signal is
the fresh filing window rather than a permanent fundamental quality filter.

## Frozen signals

For every point-in-time eligible daily VCP setup, enter at the next open after
the first close for which the latest comparable 10-Q/10-K:

- has `filed < signal_date` and was filed no more than 30 calendar days ago;
- reports diluted EPS YoY growth of at least 20%; and
- reports revenue YoY growth of at least 10%.

Current and prior facts must occur in the same accession; missing comparisons
fail closed. Do not use a ridge score. Exit at the open after 20 completed
holding sessions, unless the unchanged hard stop exits earlier. This directly
matches the fixed train label and requires every close-confirmed decision to
trade no earlier than the next open.

All PIT membership, adjusted prices, cash, sizing, position/sector/ADV caps,
8% maximum entry risk, commission, slippage, and benchmark-only SPY controls
remain fixed. Count the 30-day event-window timing and fixed-20 exit as two new
multiplicity units, raising 302 -> 304.

The single 2020–2021 internal holdout must have at least 30 trades, CAGR at
least 15%, Sharpe at least 0.75, PF above 1.20, MDD better than -15%, and
positive drop-top-five expectancy. Failure closes the rule without formal
validation or untouched OOS.

