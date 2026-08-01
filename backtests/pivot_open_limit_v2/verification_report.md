# Frozen-Pivot Limit-on-Open v2 — Train-Gate Report

Generated 2026-08-01. Trial 215 was frozen before implementation/results.
Validation and untouched OOS were not accessed.

## Result: REJECT

| Corrected train cell | Trades | Net CAGR | Sharpe | MDD | PF | Drop-top-5 expectancy |
|---|---:|---:|---:|---:|---:|---:|
| Immediate detection | 198 | 0.56% | 0.145 | -8.51% | 1.115 | — |
| Pivot retest | 85 | 0.95% | 0.247 | -9.36% | 1.239 | -1.20% |
| Pivot limit-on-open | 171 | 0.38% | 0.112 | -10.18% | 1.107 | -0.81% |

The structural opening discount increased opportunity count but did not produce
selection edge. T-statistic was 0.26, PSR 60.3%, DSR 0.57% after 215 trials,
and bootstrap CAGR 5th percentile -2.23%. Conditional order-lifetime
sensitivity and validation were not run.

Primary result: `results/pivot_open_limit_train_2026-08-01_133720.json`.
