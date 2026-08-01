# Five-Day-Low Reversal Confirmation v2 — Train-Gate Report

Generated 2026-08-01. Trial 214 was frozen before implementation/results.
Validation and untouched OOS were not accessed.

## Result: REJECT

| Corrected train cell | Trades | Net CAGR | Sharpe | MDD | PF | Drop-top-5 expectancy |
|---|---:|---:|---:|---:|---:|---:|
| Immediate detection | 198 | 0.56% | 0.145 | -8.51% | 1.115 | — |
| Pivot retest | 85 | 0.95% | 0.247 | -9.36% | 1.239 | -1.20% |
| Low + reversal | 67 | 0.14% | 0.066 | -5.25% | 1.246 | -1.43% |

The reversal confirmation reduced sample and drawdown but did not improve CAGR,
Sharpe or outlier robustness. T-statistic was 0.15, PSR 56.1%, DSR 0.43% after
214 trials, and bootstrap CAGR 5th percentile -1.71%. Conditional window
sensitivity and validation were not run.

Primary result: `results/low_reversal_train_2026-08-01_133413.json`.
