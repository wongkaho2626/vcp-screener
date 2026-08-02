# Current MA60 / Slope10 / QQQ-Synchronized Regime Overlay

Classification: **DESCRIPTIVE_ONLY — validation/OOS contaminated**

## Backtest Score: 20/100 — Reject

| Component | Score | Available max |
|---|---:|---:|
| A. Statistical validity | 26 | 30 |
| B. Risk-adjusted performance | 18 | 25 |
| C. Robustness computable | 8 | 8 |
| D. Trade quality / consistency | 18 | 20 |
| Measured total | 70 | 83 |
| Normalized raw score | 84 | 100 |
| Caps applied | unresolved survivorship bias / incomplete delisted coverage → 20; no formal out-of-sample or walk-forward segment → 55 | |
| **Final score** | **20** | **100** |

The current user-directed candidate is evaluated exactly as recorded: MA60, 10-session stock-versus-SPY MA slope, false-to-true next-open entry inside the supplied calendar, 8% initial stop, +3R arm, 24% trailing stop, no timeout, and a QQQ-synchronized liquidation at each finite window-end open.

## Portfolio performance

| Partition | Signals | Trades | Period exits | CAGR | SPY CAGR | Excess CAGR | Sharpe | Sortino | Calmar | MDD | PF | Exposure |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| train | 3002 | 18 | 10 | 20.08% | 9.70% | 8.93% | 1.598 | 2.377 | 2.259 | -8.89% | 10.098 | 68.71% |
| validation | 5608 | 46 | 20 | 18.97% | 22.87% | -8.23% | 1.149 | 1.661 | 1.134 | -16.73% | 4.988 | 87.51% |
| best_available_oos | 5550 | 91 | 30 | 15.66% | 12.05% | -3.14% | 1.147 | 1.704 | 1.450 | -10.81% | 2.962 | 66.55% |
| full | 14602 | 168 | 60 | 17.33% | 15.51% | -2.07% | 1.173 | 1.706 | 0.955 | -18.16% | 3.729 | 77.71% |

## Trade quality

| Partition | Mean net | Median net | Win rate | Worst | Mean SPY | Mean excess | Excess t | Excess CI | Drop-best-5 | Avg hold |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| train | 33.28% | 19.75% | 50.00% | -8.62% | 15.39% | 17.89% | 1.98 | [1.93, 35.89] | 8.38% | 240.44 |
| validation | 15.47% | -2.08% | 45.65% | -8.18% | 22.73% | -7.26% | -1.26 | [-16.92, 5.57] | 5.06% | 155.65 |
| best_available_oos | 8.47% | -4.77% | 46.15% | -16.53% | 9.87% | -1.40% | -0.57 | [-5.90, 3.70] | 3.56% | 82.87 |
| full | 12.09% | -8.18% | 43.45% | -16.53% | 12.77% | -0.69% | -0.29 | [-4.89, 4.14] | 8.07% | 116.54 |

## Cost stress

| Partition | 1x CAGR | 2x | 5x | 10x |
|---|---:|---:|---:|---:|
| train | 20.08% | 19.92% | 19.43% | 18.67% |
| validation | 18.97% | 18.62% | 17.68% | 16.07% |
| best_available_oos | 15.66% | 15.05% | 14.56% | 12.51% |
| full | 17.33% | 16.96% | 16.13% | 14.34% |

## Full-period calendar years

| Year | Portfolio | SPY | Exposure-matched excess | Exposure |
|---|---:|---:|---:|---:|
| 2016 | 12.54% | 8.43% | 4.07% | 99.48% |
| 2017 | 38.56% | 21.71% | 14.02% | 99.99% |
| 2018 | -10.51% | -4.57% | 1.06% | 42.85% |
| 2019 | 27.82% | 31.22% | -3.57% | 99.91% |
| 2020 | 19.73% | 18.33% | -17.92% | 93.52% |
| 2021 | 20.50% | 28.73% | -1.10% | 91.25% |
| 2022 | 9.75% | -18.18% | 2.94% | 41.33% |
| 2023 | 11.69% | 26.18% | -3.81% | 42.46% |
| 2024 | 16.61% | 24.89% | -6.49% | 96.76% |
| 2025 | 13.53% | 17.72% | -13.23% | 73.39% |
| 2026 | 17.81% | 10.09% | 7.64% | 91.05% |

## Statistical and robustness diagnostics

- Daily-return t-statistic: 3.703.
- Effective sample size: 2511.0.
- PSR versus zero: 99.99%.
- Approximate DSR probability across 575 declared trials: 72.56%.
- Block-bootstrap CAGR 90% interval: 9.27% to 25.79%.
- Monte Carlo MDD 90% interval: -32.86% to -14.20%.
- Positive months: 55.83%.

## Bias assessment

| Risk | Assessment | Evidence |
|---|---|---|
| Lookahead | Absent in implementation | QQQ close-confirmed state change executes at the next open; stock entries and exits use that same executable session boundary. |
| Survivorship | Unresolved | PIT membership is enforced, but coverage is incomplete and some former/delisted members have no bars. |
| Data snooping | Present | The QQQ rule is independently defined, but its parameters were tuned through 2026-07-02; applying it here is not untouched OOS. |
| Transaction costs | Included | 5 bps commission plus 5 bps slippage each way at 1x; 2x/5x/10x stress reported. |
| Liquidity | Partially controlled | Existing ADV capacity constraints are retained; missing histories remain a limitation. |
| Untouched OOS | Absent | Every available chronological partition is contaminated for this newly combined specification. |

## Interpretation

This run measures the current configuration but cannot validate it. The 10-session slope was selected after a train grid and failed validation; the exact calendar and this exit-policy comparison are also post-hoc. Give primary weight to exposure-matched excess, outlier trims, cost stress and the absence of untouched OOS, not raw CAGR.

## Reproduction

```bash
.venv/bin/python scripts/current_ma60_candidate_backtest.py --price-csv SP500_PIT_2016_2026.csv --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json --membership-csv scripts/data/sp500_membership.csv --sector-json scripts/data/sp500_constituents.json --output-dir backtests/qqq_synchronized_regime_v2/results --iterations 1000 --qqq-synchronized-exit
```
