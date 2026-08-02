# Trial 544 — MA60-Only, 8% Hard Stop then 3R-Armed 24% Trail

Status: **frozen before strategy returns were calculated** on 2026-08-02.

## Research question

For the Trial 542 standalone relative-MA60 entry, does retaining the initial
8% hard stop until a position closes at +3R, then switching to a wide 24%
trailing stop with no timeout, improve performance?

This is one new user-requested exit experiment. Declared multiplicity rises
from 542 to **543**. All available partitions are contaminated by prior
research and are not untouched OOS.

## Unchanged entry and portfolio

Reuse Trial 542 false-to-true entries exactly:

```python
stock_close > stock_ma60
and stock_ma60_slope_20d > 0
and stock_ma60_slope_20d > spy_ma60_slope_20d
```

Signals confirm after the close, fill at the next ticker open, and require PIT
S&P 500 membership on signal and fill. Equal 10% targets, same-open relative-
slope priority, $100,000 capital, ten-name capacity, 30% sector cap, 1% ADV
participation, cash limits and 5 bps commission plus 5 bps slippage per side
remain unchanged. SPY is benchmark-only.

## Frozen exit state machine

At entry:

```python
initial_stop = raw_entry_open * 0.92
R = cost_loaded_entry_price - initial_stop
active_stop = initial_stop
armed = False
```

The raw-open stop is identical across cost-stress multipliers. Remove the
60-session timeout completely.

For every later session, first test the stop already confirmed through the
prior close. If the low breaches it, sell at `min(open, active_stop)` and apply
exit costs. If no exit occurs:

```python
highest_close = max(highest_close, current_close)
if not armed and current_close >= entry_price + 3.0 * R:
    armed = True
if armed:
    active_stop = max(active_stop, highest_close * 0.76)
```

Arming and ratcheting happen after current-session stop evaluation, so their
levels are active only from the next session. The stop never decreases. Before
+3R the stop remains the initial 8% hard stop. Remaining positions are sold at
the final available close only for partition accounting.

The 3R trigger, 24% trailing distance, completed-close watermark, no-timeout
rule and gap-fill convention are fixed. Do not search nearby triggers or trail
widths.

## Reporting and decision

Run the same Trial 542 train, validation, best-available OOS and full periods,
plus 1x/2x/5x/10x costs. Compare with both the Trial 542 timeout baseline and
Trial 543 immediate 8% trail. Report CAGR, SPY/exposure-matched excess, MDD,
Sharpe, PF, win/payoff, holding time, exit reasons, arm rate, outlier trims,
calendar years and censoring.

Call `IMPROVES` only if the latest partition beats Trial 542 in absolute CAGR
and exposure-matched excess CAGR, has at least 30 trades, positive drop-best-
five expectancy, positive 5x-cost CAGR, and MDD no worse by more than two
percentage points. Otherwise classify `INCONCLUSIVE` or `WORSENS`.

No 2000–2005 data may be accessed.
