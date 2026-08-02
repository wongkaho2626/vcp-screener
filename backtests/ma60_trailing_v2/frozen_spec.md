# Trial 543 — Standalone Relative-MA60 with 8% Trailing Stop

Status: **frozen before trailing-strategy returns were calculated** on
2026-08-02.

## Research question

Does removing the 60-session timeout and holding the Trial 542 standalone
relative-MA60 entries until an 8% trailing stop improve chronological and
best-available OOS performance?

This is one new user-requested exit experiment. Declared multiplicity rises
from 541 to **542**. All partitions are already contaminated by prior research;
none may be described as untouched OOS.

## Entry and portfolio controls

Reuse Trial 542 signals exactly:

```python
stock_close > stock_ma60
and stock_ma60_slope_20d > 0
and stock_ma60_slope_20d > spy_ma60_slope_20d
```

Only false-to-true transitions signal, after the close, with next-ticker-open
execution and PIT membership on signal and fill. Continue to use equal 10%
targets, same-open relative-slope priority, $100,000 capital, ten-name capacity,
30% sector cap, 1% ADV participation, cash limits, and 5 bps commission plus
5 bps slippage per side. SPY remains benchmark-only.

## Frozen trailing exit

- Initial stop: 8% below the raw entry open, independent of cost multiplier.
- Remove the 60-session timeout completely.
- At the start of each session, the active stop is the greatest stop confirmed
  from information available through the prior close.
- If the current low breaches it, sell at `min(current_open, active_stop)` and
  apply exit costs.
- If no exit occurs, update the completed-close watermark and ratchet:

```python
highest_close = max(highest_close, current_close)
active_stop = max(active_stop, highest_close * 0.92)
```

- A ratchet calculated from today's close becomes active only next session;
  it cannot be applied retroactively to today's low.
- The stop never decreases. Remaining positions are liquidated at the final
  available close only for accounting.

The 8% distance, close watermark and gap-fill convention are fixed. No high-
watermark alternative, ATR distance, breakeven rule, profit target, time exit,
or parameter sensitivity is searched.

## Reporting and decision

Run the identical Trial 542 train, validation, best-available OOS and full
partitions, plus 1x/2x/5x/10x costs. Compare directly with Trial 542 on CAGR,
SPY/exposure-matched excess, MDD, Sharpe, PF, trades, hold time, stop rate,
outlier trims and calendar years.

Call the exit `IMPROVES` only if the latest partition improves absolute CAGR
and exposure-matched excess CAGR over Trial 542, keeps at least 30 trades,
has positive drop-best-five expectancy, survives 5x costs, and does not worsen
MDD by more than two percentage points. Otherwise use `INCONCLUSIVE` or
`WORSENS`. Preserve JSON, Markdown and partition-level signal/trade/equity CSVs.

No 2000–2005 data may be accessed.
