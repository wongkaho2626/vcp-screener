# Failed-Breakout Pivot Reclaim v2 — Train-Gate Report

Generated 2026-08-01. Trial 207 was frozen before implementation/results.
Validation and untouched OOS were not accessed.

## Result: REJECT

| Train cell (2016-07-01 to 2021-12-31) | Trades | Net CAGR | Sharpe | Sortino | Calmar | MDD | PF | Drop-top-5 expectancy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Pivot-retest baseline | 34 | 1.77% | 0.627 | 1.105 | 0.606 | -2.91% | 2.104 | -0.53% |
| Pivot reclaim | 30 | 1.55% | 0.573 | 1.026 | 0.462 | -3.37% | 1.842 | -1.68% |

The candidate reached exactly 30 trades and retained PF above 1.2, but failed
the CAGR, Sharpe and outlier-trim checks. Its t-statistic was 1.33, PSR 93.1%,
approximate DSR 3.93% after 207 declared trials, and block-bootstrap CAGR 5th
percentile -0.26%. Prespecified window sensitivity was conditional on a full
train pass and was not run.

PIT coverage was 91.31%, SPY remained benchmark-only, and 42 out-of-membership
train detections were removed. All signals use completed closes with next-open
fills and ignore `forward_outcome`.

Primary result: `results/pivot_reclaim_train_2026-08-01_124339.json`.
