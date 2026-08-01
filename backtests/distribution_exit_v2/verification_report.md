# Distribution-Cluster Exit v2 — Train-Gate Report

Generated 2026-08-01. Trial 210 was frozen before implementation/results.
Validation and untouched OOS were not accessed.

## Result: REJECT

| Train cell | Trades | Net CAGR | Sharpe | Sortino | Calmar | MDD | PF | Drop-top-5 expectancy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline exit | 55 | 2.39% | 0.655 | 1.034 | 0.331 | -7.22% | 1.850 | 0.43% |
| Distribution exit | 57 | 0.92% | 0.448 | 0.651 | 0.263 | -3.51% | 1.738 | -0.56% |

Forty-seven distribution exits had PF 4.558 and expectancy +3.99%, but the rule
sold most positions early and removed the long right tail. Drawdown improved,
yet CAGR, Sharpe and top-five robustness all failed the frozen gate. Candidate
t-statistic was 1.01, PSR 84.3%, DSR 3.99% after 210 trials, and bootstrap CAGR
5th percentile -0.30%. Count/window sensitivities and validation were not run.

PIT coverage was 91.31%, SPY was benchmark-only, and 42 out-of-membership
detections were removed. Exit signals use completed OHLCV bars and fill at the
following open; the resting stop retains intraday priority.

Primary result: `results/distribution_exit_train_2026-08-01_130145.json`.
