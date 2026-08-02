# Trial 522–541 — Relative-MA Period Grid

Status: **frozen before any grid-period signal count or return is calculated**
on 2026-08-02.

## Grid and unchanged signal logic

This is a discovery-only grid over exactly twenty simple-moving-average
periods:

```python
MA_PERIODS = range(10, 201, 10)  # 10, 20, ..., 200
SLOPE_SESSIONS = 20              # fixed, not searched
```

For each MA period, use stock and real SPY adjusted closes on identical actual
common dates no later than the frozen VCP pullback `signal_date`. Require
`ma_period + 20` common observations and calculate each MA's normalized
20-session percentage change. The gate remains:

```python
stock_close > stock_ma_now
and stock_ma_slope_pct > 0
and stock_ma_slope_pct > spy_ma_slope_pct
```

Comparisons are strict. A declining stock MA never qualifies. The signal can
only remove the unchanged next-open order. No threshold, slope window, EMA,
ranking rule, exit, stop, cost, size or portfolio constraint is searched.

## Multiplicity and known contamination

All twenty displayed cells count. Declared multiplicity rises from 520 to
**540**. MA50 has already been opened in Trial 521; including it again does not
restore independence and is still counted. This grid is exploratory and may
not be presented as prespecified proof.

## Train-only selection rule

Evaluate the grid only on train/discovery, 2016-07-01 through 2018-06-30. The
2018H2 embargo is not used. A cell is eligible to become the frozen candidate
only if it simultaneously has:

1. at least 20 executed train trades;
2. net train CAGR strictly above the unchanged baseline;
3. exposure-matched excess CAGR strictly above baseline;
4. higher mean matched-SPY excess among qualifying baseline trades than among
   rejected baseline trades; and
5. positive net expectancy after removing its five largest winners.

Among eligible cells only, select the largest exposure-matched excess CAGR
lift; exact ties choose the shorter MA. If no cell satisfies all five gates,
select nothing and keep validation/best-available OOS sealed. The highest
objective cell with at least 20 trades may be reported as a non-qualifying
diagnostic leader and scored with all 540 declared trials, but cannot advance.

If a cell qualifies, freeze its period before opening validation. Validation
must repeat all five directional gates, have at least 30 trades and not worsen
MDD by more than two percentage points. Only then may the contaminated
2022–2026Q1 best-available OOS and 2x/5x/10x costs be opened.

## Data, execution and reporting

Preserve the frozen VCP detection, MA20 pullback entry, next-open fill, Edge
Rank priority/sizing, capital, ten-name capacity, sector/name/ADV/cash limits,
costs, stop and 60-session exit. Enforce PIT membership on detection, signal
and fill. SPY is comparator/benchmark only and synthetic SPY is rejected.

Save the complete train grid table, signal/trade/equity CSVs, missing-history
counts, matched cohort statistics, JSON, Markdown, reproduction command and
A/B/C/D score. Report the family as `NO_QUALIFYING_WINNER`, `VALIDATION_FAIL`,
`IMPROVES`, `INCONCLUSIVE` or `WORSENS` according to the sequential evidence.

No 2000–2005 data may be accessed or required.
