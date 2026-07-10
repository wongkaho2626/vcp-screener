# Frozen VCP Strategy v1

Frozen on 2026-07-10 before the portfolio-level validation run in this repository.
This specification must not be changed in response to the validation results. Any change
creates a new version and restarts the out-of-sample clock.

## Purpose

VCP detections are candidate-generation events, not sufficient standalone buy signals.
Version 1 combines only the two previously documented execution-layer findings:

1. MA20 pullback entry after a confirmed pivot breakout.
2. Causal Edge Rank v2 as a capped position-size tilt.

No legacy composite-score, trend-template, volume, breadth, or discretionary gate is used.

## Signal and entry

- Universe membership must be point-in-time when the data source supports it.
- A setup originates from the default VCP detector parameters recorded in the source
  backtest artifact.
- After the first close above the pivot, wait at most 15 trading bars.
- Enter only on the first later bar whose low touches the contemporaneous 20-day simple
  moving average and whose close finishes at or above that average.
- A close below the pattern stop while waiting invalidates the setup.
- The simulated fill is the next session's open. If it is unavailable, skip the trade.

## Sizing and portfolio constraints

- Edge Rank v2 is computed using only same-date cross-sectional information:
  `0.70 * percentile(12-month relative strength)` plus
  `0.30 * percentile(inverse SMA50 extension)`.
- Skip Edge Rank below 30.
- Desired weights are linear in Edge Rank and capped at 1.5 times the equal-slot weight.
- Maximum 10 concurrent positions.
- Maximum initial position value is 1% of the security's trailing 20-day average dollar
  volume. A missing or non-positive ADV invalidates the order.
- Maximum two concurrent positions per known sector. Unknown sectors share one sector bucket.
- Unallocated capital remains cash; positions are not levered.

## Risk and exit

- Initial stop is the higher of the final-contraction low and 8% below the actual fill.
- Exit on the next session's open after a close below the stop.
- Otherwise exit on the next session's open after 60 holding bars.
- Positions are marked daily using adjusted close where available.
- No profit target, trailing stop, breadth gate, or exit-family selection is permitted.

## Costs

- Baseline explicit cost: 10 basis points per side.
- Market-impact stress cases: 20, 50, and 100 basis points per side.
- Costs apply to both entry and exit notional.

## Validation contract

- Primary metric: daily portfolio excess return versus SPY.
- Report raw and excess CAGR, Sharpe, Sortino, Calmar, maximum drawdown, Ulcer Index,
  distribution diagnostics, autocorrelation-adjusted sample size, PSR, DSR, and block
  bootstrap confidence intervals.
- Walk-forward results and all universe replications must be reported, including failures.
- The declared multiple-testing count is at least 108 parameter combinations plus the
  documented gate, exit, entry, breadth, and sizing variants; analysis may use a higher
  conservative count but never a lower one.
- Any later parameter or rule change is research for `v2`, not an amendment to `v1`.

## Known data limitation

Yahoo and the local current-constituent CSV do not constitute a fully
survivorship-bias-free security master. Results using them retain that limitation until a
licensed dataset containing delisted securities and point-in-time membership is supplied.
