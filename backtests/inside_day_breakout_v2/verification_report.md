# Post-Breakout Inside-Day v2 — Train-Gate Report

Generated 2026-08-01. Trial 208 was declared before implementation/results.
Validation and untouched OOS were not accessed.

## Result: REJECT

| Train cell (2016-07-01 to 2021-12-31) | Trades | Net CAGR | Sharpe | Sortino | Calmar | MDD | PF | Drop-top-5 expectancy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Pivot-retest baseline | 34 | 1.77% | 0.627 | 1.105 | 0.606 | -2.91% | 2.104 | -0.53% |
| Inside-day entry | 45 | 0.18% | 0.077 | 0.106 | 0.023 | -8.03% | 1.521 | -0.93% |

Only trade count and PF passed. The candidate's t-statistic was 0.17, PSR
56.9%, approximate DSR 0.46% after 208 declared trials, and block-bootstrap
CAGR 5th/median/95th percentiles were -1.64% / 0.20% / 2.22%. The result is
outlier-dependent and materially worse than pivot-retest. Conditional 5/15-day
sensitivity was not run after the failed train gate.

PIT member-day coverage was 91.31%; SPY was benchmark-only and 42 detections
outside their membership intervals were removed. Completed-bar confirmation,
next-open fills and non-use of `forward_outcome` are unit-tested.

Primary result: `results/inside_day_breakout_train_2026-08-01_124731.json`.
