# Trial 520 — Positive MA50 Slope Confirmation Gate

Status: **frozen before calculating MA50-slope signal counts or accessing any
Trial 520 trade return, portfolio return, validation result or best-available
OOS result** on 2026-08-02.

## Known evidence before freeze

- The frozen pullback baseline and its counts/results have already been opened
  by prior research.
- Trial 505–518's 20-session stock-minus-SPY gate was inconsistent and its
  Trial 519 descriptive audit was `INCONCLUSIVE`.
- Price above SMA50 is already one of seven Trend Template criteria, while the
  template passes with six of seven. Rising SMA200 is also a criterion.
- Generic trend-path, MA support/exit and 20-session OLS-slope families have
  previously failed. MA50 slope is therefore a low-prior, overlapping trend
  hypothesis rather than a new orthogonal information source.

## Frozen hypothesis

For each otherwise eligible frozen VCP pullback order, use adjusted closes
available by the existing `signal_date` close. Let:

```python
sma50_now = mean(close[t-49:t+1])
sma50_20_sessions_ago = mean(close[t-69:t-19])

positive_ma50_slope = (
    close[t] > sma50_now
    and sma50_now > sma50_20_sessions_ago
)
```

Both comparisons are strict. The current price and both averages use the
stock's actual valid trading sessions no later than `signal_date`. At least 70
valid observations are required. Do not backfill from the future. A weekend or
holiday as-of resolves to the latest completed stock session. The fill remains
the existing next-session open; entry-day close is never used.

The primary challenger is:

```text
unchanged frozen VCP pullback order
AND close above SMA50
AND SMA50 today above SMA50 20 stock sessions ago
```

The negative control contains available baseline orders failing either strict
condition. Missing-history orders remain in baseline but in neither cohort.

## What remains unchanged

- VCP detection, pivot, existing MA20 pullback signal and next-open timing;
- Edge Rank priority and sizing;
- initial cash, maximum ten positions, name/sector/ADV/cash limits;
- commission, slippage, stop, 60-session timeout and all risk constraints;
- point-in-time membership at detection, signal and fill;
- SPY as benchmark only, never a holding or fallback.

Attach `ma50_period`, `ma50_slope_sessions`, `signal_close`, `ma50_value`,
`ma50_20_sessions_ago`, `ma50_slope_pct`, `positive_ma50_slope`,
`ma50_signal_date` and any missing-history reason to evaluated signals/trades.

## Evidence design

Trial 520 has one strategy hypothesis and raises declared multiplicity from 518
to **519**. No alternative MA length, slope window or threshold is searched.

- Train/discovery: 2016-07-01 through 2018-06-30.
- Embargo: 2018-07-01 through 2018-12-31.
- Validation: 2019-01-01 through 2021-12-31.
- Capped best-available OOS: 2022-01-01 through 2026-03-31.

All three fixed partitions are evaluated because the user explicitly requested
the already-prespecified single rule and no parameter selection occurs between
folds. The latest partition is contaminated by prior research and cannot be
called untouched OOS.

For baseline, challenger and negative control, report actual portfolio and
trade metrics, matched-window SPY excess, calendar years, top/bottom-five trim,
winsorization, bootstrap confidence intervals, clustered inference, PSR/DSR,
block bootstrap and Monte Carlo. Stress baseline and challenger at 2x, 5x and
10x costs. Save signal, trade and equity CSVs plus JSON and Markdown.

## Decision rule

`IMPROVES` requires the primary to improve matched-SPY trade evidence and
portfolio risk-adjusted results in both validation and best-available OOS,
retain at least 30 OOS trades, remain positive after costs and removal of the
five largest winners, avoid materially worse MDD, and show directionally
supportive train evidence. Mixed evidence is `INCONCLUSIVE`. Consistently
negative lift with worse OOS matched excess is `WORSENS`.

The score must show A/B/C/D, normalization, every cap and the final value. No
2000–2005 data may be accessed or required.
