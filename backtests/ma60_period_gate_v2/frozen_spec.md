# Trial 551–568 — User-Supplied MA60 Entry-Date Windows

Status: **frozen before gated portfolio returns were calculated** on
2026-08-02.

## Research question

Does allowing the current Trial 544 MA60 strategy to open positions only
during the following user-supplied calendar windows change performance?

| Start | End |
|---|---|
| 2002-07-24 | 2002-08-15 |
| 2002-10-10 | 2002-11-12 |
| 2003-01-10 | 2003-03-18 |
| 2004-03-25 | 2004-06-14 |
| 2005-03-31 | 2007-07-27 |
| 2008-01-23 | 2008-09-30 |
| 2008-10-17 | 2008-11-05 |
| 2008-11-24 | 2009-01-14 |
| 2009-02-02 | 2009-02-18 |
| 2009-03-09 | 2011-09-19 |
| 2011-10-06 | 2014-08-08 |
| 2015-08-25 | 2018-03-23 |
| 2018-10-15 | 2020-02-26 |
| 2020-03-16 | 2021-12-01 |
| 2022-06-14 | 2022-11-14 |
| 2023-01-27 | 2023-05-02 |
| 2023-10-30 | 2024-12-19 |
| 2025-04-07 | open |

## Exact interpretation

The actual fill/entry date must fall inside a listed interval, inclusive of
both finite endpoints. The last interval has no end. A signal before a window
may fill inside it. A position opened inside a window remains governed by the
normal exit after the window closes; the calendar gate does not force a sale.

All other entry logic is unchanged: standalone MA60 false-to-true transition,
stock close above SMA60, positive 20-session SMA60 percentage slope, and stock
slope strictly above SPY's aligned SMA60 slope. Signals remain close-confirmed
and fill no earlier than the next eligible ticker open with point-in-time
membership on signal and fill.

## Unchanged exit and portfolio

- 8% initial hard stop below raw entry open.
- Arm after a completed close reaches cost-loaded entry + 3R.
- Once armed, ratchet to 24% below the highest completed close, active from the
  next session.
- No timeout and no calendar-boundary liquidation.
- Fixed capital, sizing, ten-position capacity, sector/name/ADV/cash limits,
  commission and slippage. SPY remains benchmark-only.

## Executable coverage and classification

The repository's executable price input contains 2014 lookback data and
supports strategy signals only from 2016 onward. Raw 2006–2015 execution data
and every 2002–2005 period are absent. Consequently only the seven windows
from 2015-08-25 onward overlap executable strategy periods; earlier windows
must be reported as untested, not empty or losing.

The origin of these precise dates has not been established. They may encode
future market outcomes and all overlapping periods have already been used in
research. This run is therefore **descriptive and potentially lookahead**, not
an OOS validation or deployable calendar rule. It may answer how historical
performance changes but cannot prove improvement.

Each of the 18 supplied intervals counts as at least one multiplicity unit, a
conservative lower bound because the endpoints themselves are free choices.
Declared multiplicity rises from 549 to **567**.

## Reporting

Run train, validation, best-available OOS and full portfolio paths with the
same boundaries as Trial 544, plus 1x/2x/5x/10x costs. Compare identical
partition baselines and report signals retained, trades, CAGR, total return,
SPY and exposure-matched excess, volatility, Sharpe, Sortino, Calmar, MDD,
exposure, utilization, turnover, PF, win rate, holding time, exit/arm counts,
bootstrap confidence intervals, outlier trims, calendar years and right-
censored exits. Save JSON, Markdown and signal/trade/equity CSV files.

For diagnostic context, evaluate the usual six economic checks against Trial
544, but the final classification remains `DESCRIPTIVE_ONLY` regardless of the
numbers. No untested window may be filled with external or reconstructed data,
and no 2000–2005 lookup may be performed.
