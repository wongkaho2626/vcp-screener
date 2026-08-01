# Detection-Anchored Five-Day-Low Pullback v2 — Train-Gate Report

Generated 2026-08-01. Trial 213 was frozen before implementation/results.
Validation and untouched OOS were not accessed.

## Result: REJECT

| Corrected train cell | Trades | Net CAGR | Sharpe | MDD | PF | Drop-top-5 expectancy |
|---|---:|---:|---:|---:|---:|---:|
| Immediate detection | 198 | 0.56% | 0.145 | -8.51% | 1.115 | — |
| Pivot retest | 85 | 0.95% | 0.247 | -9.36% | 1.239 | -1.20% |
| Five-day closing low | 182 | 0.26% | 0.079 | -8.38% | 1.171 | -0.71% |

The candidate passed only sample size. It produced many entries but did not
distinguish temporary pullbacks from falling knives. T-statistic was 0.18, PSR
57.3%, approximate DSR 0.46% after 213 trials, and bootstrap CAGR 5th
percentile -2.60%. Conditional 3/10-day sensitivity and validation were not run.

The run uses corrected adjusted detections, as-of stop invalidation, PIT
membership (40 train drops), benchmark-only SPY and unchanged portfolio/cost
constraints. Primary result:
`results/five_day_low_train_2026-08-01_133138.json`.
