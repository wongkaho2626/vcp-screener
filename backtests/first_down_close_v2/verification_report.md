# First Post-Breakout Down-Close v2 — Train-Gate Report

Generated 2026-08-01. Trial 205 was declared before implementation/results.
Validation and untouched OOS were not accessed.

## Result: REJECT

| Train cell (2016-07-01 to 2021-12-31) | Trades | Net CAGR | Sharpe | Sortino | Calmar | MDD | PF | Drop-top-5 expectancy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Pivot-retest baseline | 34 | 1.77% | 0.627 | 1.105 | 0.606 | -2.91% | 2.104 | -0.53% |
| First down-close | 64 | 1.45% | 0.374 | 0.563 | 0.170 | -8.52% | 1.629 | 0.03% |

The candidate passed trade count, PF and the top-five trim, but failed both
required improvement checks. Its larger drawdown and lower risk-adjusted return
show that waiting for any ordinary post-breakout pause is not selective enough.
The frozen 5/15-session sensitivity was conditional on a train pass and was
therefore not run.

PIT member-day coverage was 91.31%; SPY remained benchmark-only. Forty-two
out-of-membership detections were excluded. The signal is confirmed at a
completed close, filled at the next open, and never reads `forward_outcome`.

Primary machine-readable result:
`results/first_down_close_train_2026-08-01_123558.json`.
