# Loss-Only Distribution-Cluster Exit v2 — Train-Gate Report

Generated 2026-08-01. Trial 211 was declared before implementation/results.
Validation and untouched OOS were not accessed.

## Result: REJECT

| Train cell | Trades | Net CAGR | Sharpe | Sortino | Calmar | MDD | PF | Drop-top-5 expectancy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Baseline exit | 55 | 2.39% | 0.655 | 1.034 | 0.331 | -7.22% | 1.850 | 0.43% |
| Loss-distribution exit | 55 | 0.66% | 0.273 | 0.379 | 0.130 | -5.10% | 1.597 | -0.63% |

Thirty-two qualifying exits had PF 0.109, expectancy -2.07% and 18.8% win
rate. Waiting for both a distribution cluster and a close below entry simply
realized laggard losses; it did not preserve the baseline's right tail. CAGR,
Sharpe, trim robustness and attributed-exit PF all failed. Candidate PSR was
73.0%, DSR 1.58% after 211 trials, and bootstrap CAGR 5th percentile -1.06%.
No sensitivity or validation was run.

PIT coverage was 91.31%, SPY was benchmark-only, and 42 non-member detections
were excluded. Signals are close-confirmed and execute at the next open, with
the unchanged resting stop retaining priority before signal formation.

Primary result: `results/loss_distribution_exit_train_2026-08-01_130449.json`.
