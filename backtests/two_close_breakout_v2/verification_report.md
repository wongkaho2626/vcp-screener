# Two-Close Breakout Confirmation v2 — Train-Gate Report

Generated 2026-08-01. Hypothesis declared as trial 204 before implementation
or results. This report is train-only; validation and untouched OOS remain
sealed.

## Result: REJECT

| Train cell (2016-07-01 to 2021-12-31) | Trades | Net CAGR | Sharpe | Sortino | Calmar | MDD | PF | Drop-top-5 expectancy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Pivot-retest baseline | 34 | 1.77% | 0.627 | 1.105 | 0.606 | -2.91% | 2.104 | -0.53% |
| Two-close confirmation | 56 | 0.79% | 0.279 | 0.390 | 0.135 | -5.87% | 1.521 | -0.11% |

The candidate passed only the trade-count and PF checks. It failed to improve
CAGR or Sharpe and became negative after removing the five largest winners.
The prespecified train gate therefore failed. No one-close/three-close
sensitivity was run because the frozen specification permits those diagnostics
only after a train pass.

Point-in-time coverage was 91.31% of member-days, SPY was benchmark-only, and
42 in-period detections outside their membership interval were excluded. The
causal implementation confirms two closes using only completed bars and fills
at the following open. It does not read `forward_outcome`.

Primary machine-readable result:
`results/two_close_breakout_train_2026-08-01_123314.json`.
