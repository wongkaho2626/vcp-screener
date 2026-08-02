# Trial 521 — Stock-versus-SPY MA50 Slope Gate

Status: **frozen before calculating Trial 521 signal counts or accessing any
Trial 521 return** on 2026-08-02.

## Prespecified hypothesis

For every otherwise eligible frozen VCP pullback order, align the stock and
real SPY adjusted-close histories on actual common trading dates no later than
the existing `signal_date`. Require 70 common observations. On the latest
common date `t` calculate:

```python
stock_ma50_now = mean(stock_close[t-49:t+1])
stock_ma50_then = mean(stock_close[t-69:t-19])
spy_ma50_now = mean(spy_close[t-49:t+1])
spy_ma50_then = mean(spy_close[t-69:t-19])

stock_ma50_slope_pct = stock_ma50_now / stock_ma50_then - 1
spy_ma50_slope_pct = spy_ma50_now / spy_ma50_then - 1

positive_relative_ma50_slope = (
    stock_close[t] > stock_ma50_now
    and stock_ma50_slope_pct > 0
    and stock_ma50_slope_pct > spy_ma50_slope_pct
)
```

All comparisons are strict. Percentage changes, not dollar slopes, are
compared. A declining stock MA50 never qualifies merely because it declines
less than SPY. Both rising qualifies only when the stock MA50 rises faster.
Stock positive while SPY falls qualifies.

The signal uses only the signal-date close or an earlier completed common
session. It may remove the existing next-open order but may not advance,
delay, resize or rerank it. Weekend/holiday as-of resolves backward; missing
dates are intersected, not forward-filled or aligned by independent indexes.

## Variants

- Baseline: every unchanged frozen VCP pullback order.
- Primary: baseline plus the strict relative MA50-slope gate above.
- Negative control: available baseline signals failing any primary condition.
- Missing stock/SPY/common history belongs to neither primary nor control.

No MA period, slope window, threshold or combination is searched. Trial 521
adds one hypothesis and raises declared multiplicity from 519 to **520**.

## Fixed strategy and data contract

VCP detection, pivot, MA20 pullback entry timing, Edge Rank priority/sizing,
capital, ten-name capacity, name/sector/ADV/cash limits, two-sided costs,
initial stop, 60-session timeout and risk constraints remain unchanged. PIT
membership is required at detection, signal and fill. SPY is benchmark-only
and can never be held. Synthetic SPY is rejected. CSVClient's adjusted-close
convention is applied identically to stock and SPY.

Attach the MA period/window, stock signal close, both current/prior averages,
both percentage slopes, slope divergence, Boolean result, actual common signal
date and missing reason to every evaluated signal/trade.

## Chronology and decision

- Train: 2016-07-01 through 2018-06-30.
- Embargo: 2018-07-01 through 2018-12-31.
- Validation: 2019-01-01 through 2021-12-31.
- Capped best-available OOS: 2022-01-01 through 2026-03-31.

All three fixed partitions are evaluated without tuning between them. The
latest partition is already contaminated by prior research and is not genuine
untouched OOS.

Report actual portfolio/trade metrics, baseline qualifying-versus-rejected
matched SPY excess, calendar years, top/bottom-five trim, winsorization,
bootstrap/clustered inference, PSR/DSR, block bootstrap, Monte Carlo and
2x/5x/10x cost stress. Save JSON, Markdown and signal/trade/equity CSVs.

`IMPROVES` requires supportive train direction plus improved validation and
best-available OOS stock-selection/excess and risk-adjusted portfolio evidence,
at least 30 OOS trades, positive OOS CAGR after baseline and 5x costs, positive
drop-best-five expectancy and no materially worse MDD. Mixed evidence is
`INCONCLUSIVE`; consistently adverse evidence is `WORSENS`.

Score A/B/C/D with every applicable cap. No 2000–2005 data may be accessed.
