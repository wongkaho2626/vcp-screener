# Trial 545–550 — Standalone MA10–60 Grid with Frozen 3R-Armed Exit

Status: **frozen before any MA10–50 portfolio return was calculated** on
2026-08-02. MA60 outcomes are already known from Trial 544 and remain counted.

## Research question

Keeping Trial 544's exit and every portfolio constraint unchanged, does a
shorter stock-versus-SPY relative moving-average period improve the standalone
entry strategy?

## Six-cell buy grid

```python
MA_PERIODS = (10, 20, 30, 40, 50, 60)
SLOPE_SESSIONS = 20
```

For each cell, stock and SPY adjusted closes are aligned on actual common
completed sessions no later than date `t`. Calculate the percentage slope of
each simple moving average over exactly 20 common sessions. The condition is:

```python
stock_close[t] > stock_ma[t]
and stock_ma_slope_20d > 0
and stock_ma_slope_20d > spy_ma_slope_20d
```

A buy signal occurs only when that cell's condition changes from false to
true. It fills no earlier than the ticker's next eligible open and requires
point-in-time S&P 500 membership on signal and fill dates. Same-open candidates
retain the existing relative-slope priority. No VCP, MA20 pullback, Edge Rank,
extra filter, EMA, threshold, ranking alternative, or slope-window search is
introduced.

## Unchanged exit and portfolio

- Initial stop: 8% below raw entry open, identical across cost multipliers.
- `R = cost_loaded_entry_price - initial_stop`.
- Before a completed close reaches entry + 3R, only the initial stop applies.
- Once armed, the next session's stop is the greater of the existing stop and
  76% of the highest completed close; it never decreases.
- No timeout. End-of-partition liquidation is right-censored accounting.
- $100,000 initial capital, 10% target position, ten-name capacity, 30% sector
  cap, 1% ADV participation, cash limits, and 5 bps commission plus 5 bps
  slippage per side remain fixed. SPY is benchmark-only.

## Multiplicity and sequential selection

All six displayed periods count as new requested cells. Declared multiplicity
rises from 543 to **549**. Prior MA-period and MA60 outcomes mean this family is
exploratory, not independent confirmation.

Run the six cells first on train/discovery, 2016-07-01 through 2018-06-30.
A train cell qualifies only if all conditions hold:

1. at least 15 completed trades (the frozen no-timeout portfolio completed
   only 18 MA60 train trades);
2. net CAGR > 0;
3. exposure-matched excess CAGR > 0;
4. net profit factor > 1.2;
5. maximum drawdown better than -30%; and
6. positive net expectancy after removing the five best trades.

Among qualified cells, select the highest exposure-matched excess CAGR; exact
ties choose the shorter MA. If none qualifies, stop and keep later periods
sealed. The threshold of 15 is a feasibility floor, not proof of adequacy; the
under-30-trades score cap still applies.

The selected cell opens validation only. Validation must have at least 30
trades and repeat conditions 2–6. Only then open best-available OOS. The OOS
cell is `IMPROVES` only if, relative to the frozen Trial 544 MA60 incumbent, it:

1. improves CAGR;
2. improves exposure-matched excess CAGR;
3. has at least 30 completed trades;
4. has positive drop-best-five expectancy;
5. has positive CAGR at 5x costs; and
6. does not worsen MDD by more than two percentage points.

Otherwise report `INCONCLUSIVE` or `WORSENS`. A diagnostic train leader cannot
be substituted after seeing validation or OOS.

## Evidence and output

Report every train cell, exit-state counts, missing history, trade count, CAGR,
exposure-matched excess CAGR, Sharpe, Sortino, Calmar, MDD, PF, average hold,
drop-best-five expectancy and score. For any partition legally opened, save
signals, trades, daily equity, calendar years, bootstrap statistics, costs and
exact commands. Enforce the existing 91.31% coverage gate and disclose
survivorship/delisted limitations.

Do not access or require 2000–2005 data.
