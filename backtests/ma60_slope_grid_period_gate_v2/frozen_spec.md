# Trial 569–572 — MA60 Slope-Window Grid inside Supplied Calendar

Status: **frozen before any new 10/30/40-session slope return was calculated**
on 2026-08-02. The 20-session outcome is already known and remains counted.

## Research question

Keeping the current MA60 strategy, user-supplied entry calendar, exit and
portfolio unchanged, does using a 10-, 20-, 30- or 40-common-session MA60
slope window improve chronological performance?

```python
MA_PERIOD = 60
SLOPE_WINDOWS = (10, 20, 30, 40)
```

For slope window `L`, calculate stock and SPY SMA60 percentage changes over
the same actual common completed trading sessions:

```python
stock_slope = stock_sma60[t] / stock_sma60[t-L] - 1
spy_slope = spy_sma60[t] / spy_sma60[t-L] - 1

condition = (
    stock_close[t] > stock_sma60[t]
    and stock_slope > 0
    and stock_slope > spy_slope
)
```

A signal occurs only on `False -> True`. It confirms after the close and fills
no earlier than the next eligible ticker open. PIT S&P 500 membership is
required on signal and fill. Same-open candidates remain ranked by
`stock_slope - spy_slope`.

## Unchanged calendar, exit and portfolio

The actual fill date must remain inside one of the 18 inclusive user-supplied
windows in `backtests/ma60_period_gate_v2/frozen_spec.md`; only seven overlap
executable 2016+ strategy data. Positions are not closed at window boundaries.

The exit remains an 8% initial hard stop, a completed-close +3R arm, then a
24% completed-close trailing stop active from the next session, with no
timeout. Capital, sizing, ten-name capacity, sector/name/ADV/cash constraints,
commission and slippage remain fixed. SPY is benchmark-only.

## Multiplicity and train selection

All four slope windows count as new displayed cells. Declared multiplicity
rises from 567 to **571**. Prior MA and 20-session slope research makes this
exploratory rather than independent confirmation.

Run all four cells first on train, 2016-07-01 through 2018-06-30, using the
same simulation clock as the ungated MA60 baseline. A cell qualifies only if:

1. at least 15 completed train trades;
2. net CAGR > 0;
3. exposure-matched excess CAGR > 0;
4. net profit factor > 1.2;
5. maximum drawdown better than -30%; and
6. positive net expectancy after removing the five best trades.

Among qualified cells, select the highest exposure-matched excess CAGR; exact
ties choose the shorter slope window. If no cell qualifies, stop and keep
validation/OOS sealed. The 15-trade threshold is only a feasibility floor;
under 30 remains thin and subject to the score cap.

## Sequential validation

Only the selected slope may open validation. It must have at least 30 trades
and repeat conditions 2–6. Only then may best-available OOS open. A candidate
that reaches OOS is compared with the frozen calendar-gated 20-session
incumbent and must improve OOS CAGR and exposure-matched excess CAGR, retain at
least 30 trades, have positive drop-best-five expectancy and 5x-cost CAGR, and
avoid worsening MDD by more than two percentage points.

No diagnostic leader or higher raw-CAGR cell may replace the frozen selection
after validation is viewed.

## Evidence classification

The exact calendar dates' causal provenance remains unknown and every
executable period is contaminated by prior research. Even a sequential pass
is therefore `DESCRIPTIVE_ONLY`; the slope grid cannot establish a deployable
regime rule. Report all train cells, any legally opened later partition,
signals/trades/equity CSVs, exit/arm counts, costs, bootstrap/outlier metrics,
A/B/C/D score, coverage and exact commands.

Do not access, infer or require 2000–2005 data.
