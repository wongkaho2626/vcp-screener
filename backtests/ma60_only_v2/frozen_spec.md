# Trial 542 — Standalone Relative-MA60 Entry

Status: **frozen before standalone signal counts or returns were calculated**
on 2026-08-02.

## Research question

What happens if VCP detection, breakout confirmation, the MA20 pullback entry,
and VCP Edge Rank are removed, and the stock-versus-SPY relative-MA60 condition
becomes the only entry signal?

This is a new standalone trend strategy, not a VCP challenger. Trial 541's
train grid selected no winner; MA60 is being tested only because the user
explicitly requested this diagnostic. Trial 542 adds one declared multiplicity
unit, taking the repository total from 540 to **541**.

## Entry event

On actual common stock/SPY sessions, using adjusted OHLC, calculate:

```python
stock_ma60_now = mean(stock_close[t-59:t+1])
stock_ma60_then = mean(stock_close[t-79:t-19])
spy_ma60_now = mean(spy_close[t-59:t+1])
spy_ma60_then = mean(spy_close[t-79:t-19])

stock_slope_pct = 100 * (stock_ma60_now / stock_ma60_then - 1)
spy_slope_pct = 100 * (spy_ma60_now / spy_ma60_then - 1)

condition = (
    stock_close[t] > stock_ma60_now
    and stock_slope_pct > 0
    and stock_slope_pct > spy_slope_pct
)
```

All comparisons are strict. Emit an entry signal only on a causal `False` to
`True` transition. An unavailable condition does not pass. A condition already
true before a test partition begins does not create an artificial boundary
entry. The signal is known after the close and fills no earlier than the next
ticker session's open. Both signal and fill dates must pass point-in-time S&P
500 membership.

No VCP detection, VCP breakout, MA20 pullback, pivot, contraction, pattern
stop, or Edge Rank is consulted.

## Portfolio mechanics made necessary by removing VCP

Removing VCP removes both its pattern-derived stop and Edge Rank sizing input.
Freeze these outcome-independent replacements before the run:

- use the existing 8% maximum-risk limit as the initial hard stop, measured
  from the raw next-open price so cost-stress multipliers cannot move the stop;
- target the unchanged 10% maximum position per filled name;
- when same-open candidates exceed capacity, prioritize the larger
  `stock_slope_pct - spy_slope_pct`, then ticker alphabetically;
- retain $100,000 initial capital, ten-name capacity, 30% sector cap, 1% ADV
  participation, cash constraint, 5 bps commission plus 5 bps slippage on
  each side, and the unchanged 60-session timeout;
- use the repository's current sector metadata where available and `Unknown`
  otherwise. This is not point-in-time sector classification and must be
  reported as a limitation.

This sizing is required to make a VCP-free portfolio executable and means the
result is not an apples-to-apples one-variable comparison with the frozen VCP
strategy.

## Chronological reporting

Run independently on:

- train/discovery: signals 2016-07-01 through 2018-06-30;
- validation: signals 2019-01-01 through 2021-12-31;
- best-available OOS: signals 2022-01-01 through 2026-03-31;
- full diagnostic: signals 2016-07-01 through 2026-03-31.

Keep post-partition price tails only to complete already-open trades. Report
1x, 2x, 5x, and 10x costs, calendar years, trade bootstrap, outlier trims,
portfolio metrics, SPY comparison, signal/membership exclusions, JSON, CSV and
Markdown artifacts. No 2000–2005 data may be accessed.

The latest period is only best-available OOS: extensive prior repository work
has already exposed it, and MA60 was selected after seeing the train grid.
It must not be described as untouched confirmatory evidence.
