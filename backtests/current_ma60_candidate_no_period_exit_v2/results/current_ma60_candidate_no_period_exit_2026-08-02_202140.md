# Current MA60 / Slope10 / No-Period-Exit Ablation

Classification: **DESCRIPTIVE_ONLY — validation/OOS contaminated**

## Backtest Score: 20/100 — Reject

| Component | Score | Available max |
|---|---:|---:|
| A. Statistical validity | 20 | 30 |
| B. Risk-adjusted performance | 10 | 25 |
| C. Robustness computable | 8 | 8 |
| D. Trade quality / consistency | 18 | 20 |
| Measured total | 56 | 83 |
| Normalized raw score | 67 | 100 |
| Caps applied | unresolved survivorship bias / incomplete delisted coverage → 20; no formal out-of-sample or walk-forward segment → 55 | |
| **Final score** | **20** | **100** |

The current user-directed candidate is evaluated exactly as recorded: MA60, 10-session stock-versus-SPY MA slope, false-to-true next-open entry inside the supplied calendar, 8% initial stop, +3R arm, 24% trailing stop, no timeout, with no forced liquidation when a calendar window ends. The calendar restricts entries only.

## Portfolio performance

| Partition | Signals | Trades | Period exits | CAGR | SPY CAGR | Excess CAGR | Sharpe | Sortino | Calmar | MDD | PF | Exposure |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| train | 3003 | 18 | 0 | 19.21% | 9.70% | 7.44% | 1.362 | 1.989 | 2.058 | -9.35% | 8.679 | 88.45% |
| validation | 5616 | 44 | 0 | 13.53% | 22.87% | -6.93% | 0.768 | 1.074 | 0.470 | -28.86% | 3.715 | 96.60% |
| best_available_oos | 5570 | 51 | 0 | 12.27% | 12.05% | -4.99% | 0.869 | 1.275 | 0.842 | -14.60% | 3.424 | 86.63% |
| full | 14631 | 99 | 0 | 15.16% | 15.51% | -0.92% | 0.935 | 1.329 | 0.557 | -27.24% | 5.185 | 94.28% |

## Trade quality

| Partition | Mean net | Median net | Win rate | Worst | Mean SPY | Mean excess | Excess t | Excess CI | Drop-best-5 | Avg hold |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| train | 31.60% | 7.25% | 50.00% | -8.62% | 17.23% | 14.37% | 1.39 | [-3.39, 35.35] | 4.70% | 302.50 |
| validation | 12.31% | -8.18% | 40.91% | -9.30% | 18.81% | -6.50% | -0.74 | [-19.53, 13.67] | -1.08% | 177.73 |
| best_available_oos | 10.89% | -5.55% | 47.06% | -16.53% | 18.05% | -7.16% | -1.59 | [-15.66, 2.23] | 2.18% | 194.43 |
| full | 17.61% | -4.67% | 47.47% | -16.53% | 19.25% | -1.64% | -0.32 | [-10.50, 9.35] | 9.32% | 238.54 |

## Cost stress

| Partition | 1x CAGR | 2x | 5x | 10x |
|---|---:|---:|---:|---:|
| train | 19.21% | 19.05% | 18.57% | 17.83% |
| validation | 13.53% | 13.25% | 12.33% | 11.08% |
| best_available_oos | 12.27% | 12.78% | 12.68% | 11.66% |
| full | 15.16% | 14.95% | 14.56% | 13.56% |

## Full-period calendar years

| Year | Portfolio | SPY | Exposure-matched excess | Exposure |
|---|---:|---:|---:|---:|
| 2016 | 12.54% | 8.43% | 4.07% | 99.48% |
| 2017 | 38.56% | 21.71% | 14.02% | 99.99% |
| 2018 | -4.66% | -4.57% | 0.77% | 81.85% |
| 2019 | 23.98% | 31.22% | -6.27% | 99.97% |
| 2020 | 3.35% | 18.33% | -12.33% | 98.09% |
| 2021 | 22.48% | 28.73% | -4.62% | 99.77% |
| 2022 | 14.75% | -18.18% | 31.08% | 82.74% |
| 2023 | 15.30% | 26.18% | -9.47% | 89.83% |
| 2024 | 9.49% | 24.89% | -12.03% | 97.94% |
| 2025 | 8.15% | 17.72% | -8.89% | 96.67% |
| 2026 | 11.80% | 10.09% | 2.32% | 92.10% |

## Statistical and robustness diagnostics

- Daily-return t-statistic: 2.951.
- Effective sample size: 2511.0.
- PSR versus zero: 99.82%.
- Approximate DSR probability across 574 declared trials: 44.39%.
- Block-bootstrap CAGR 90% interval: 5.89% to 24.35%.
- Monte Carlo MDD 90% interval: -40.42% to -17.89%.
- Positive months: 61.67%.

## Bias assessment

| Risk | Assessment | Evidence |
|---|---|---|
| Lookahead | Absent in implementation | Close-confirmed signal and next-ticker-open entry; no calendar boundary exit is used. |
| Survivorship | Unresolved | PIT membership is enforced, but coverage is incomplete and some former/delisted members have no bars. |
| Data snooping | Present | Slope10, exact calendar endpoints and this no-period-exit ablation were evaluated after prior validation inspection. |
| Transaction costs | Included | 5 bps commission plus 5 bps slippage each way at 1x; 2x/5x/10x stress reported. |
| Liquidity | Partially controlled | Existing ADV capacity constraints are retained; missing histories remain a limitation. |
| Untouched OOS | Absent | Every available chronological partition is contaminated for this newly combined specification. |

## Interpretation

This run measures the current configuration but cannot validate it. The 10-session slope was selected after a train grid and failed validation; the exact calendar and this exit-policy comparison are also post-hoc. Give primary weight to exposure-matched excess, outlier trims, cost stress and the absence of untouched OOS, not raw CAGR.

## Reproduction

```bash
.venv/bin/python scripts/current_ma60_candidate_backtest.py --price-csv SP500_PIT_2016_2026.csv --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json --membership-csv scripts/data/sp500_membership.csv --sector-json scripts/data/sp500_constituents.json --output-dir backtests/current_ma60_candidate_no_period_exit_v2/results --iterations 1000 --disable-period-exit
```
