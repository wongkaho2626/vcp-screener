# One-Time Pivot-Reclaim Re-entry v2 — Train-Gate Report

Generated 2026-08-01. Trial 209 was declared before implementation/results.
Validation and untouched OOS were not accessed.

## Result: REJECT

| Train cell | Trades | Net CAGR | Sharpe | Sortino | Calmar | MDD | PF | Drop-top-5 expectancy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Down-close pivot-hold baseline | 55 | 2.39% | 0.655 | 1.034 | 0.331 | -7.22% | 1.850 | 0.43% |
| One-time stop re-entry | 64 | 2.02% | 0.557 | 0.877 | 0.244 | -8.28% | 1.672 | 0.21% |

Seventeen re-entry signals were generated and 14 were admitted by the fixed
portfolio. Those re-entry trades had PF 0.423, expectancy -3.37%, 28.6% win
rate, and average win/loss +8.66%/-8.19%. They directly reduced CAGR and
Sharpe. The candidate failed three prespecified gates, so 10/30-session
sensitivity and validation were not run.

Candidate t-statistic was 1.26, PSR 90.4%, approximate DSR 5.77% after 209
declared trials, and block-bootstrap CAGR 5th percentile -0.30%.

PIT coverage was 91.31%, SPY remained benchmark-only, and 42 out-of-membership
detections were removed. Reclaims are close-confirmed and can fill only at the
following open; the engine permits at most one second attempt and keeps sizing,
costs, stop width, holding limit and all portfolio constraints unchanged.

Primary result: `results/stop_reentry_train_2026-08-01_125723.json`.
