# Current MA60 / Slope10 / Forced-Period-Exit Performance

Classification: **DESCRIPTIVE_ONLY — validation/OOS contaminated**

## Backtest Score: 20/100 — Reject

| Component | Score | Available max |
|---|---:|---:|
| A. Statistical validity | 26 | 30 |
| B. Risk-adjusted performance | 18 | 25 |
| C. Robustness computable | 8 | 8 |
| D. Trade quality / consistency | 16 | 20 |
| Measured total | 68 | 83 |
| Normalized raw score | 82 | 100 |
| Caps applied | unresolved survivorship bias / incomplete delisted coverage → 20; no formal out-of-sample or walk-forward segment → 55 | |
| **Final score** | **20** | **100** |

The current user-directed candidate is evaluated exactly as recorded: MA60, 10-session stock-versus-SPY MA slope, false-to-true next-open entry inside the supplied calendar, 8% initial stop, +3R arm, 24% trailing stop, no timeout, and an opening liquidation on the first ticker session outside all holding windows.

## Portfolio performance

| Partition | Signals | Trades | Period exits | CAGR | SPY CAGR | Excess CAGR | Sharpe | Sortino | Calmar | MDD | PF | Exposure |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| train | 3003 | 18 | 10 | 19.71% | 9.70% | 7.42% | 1.554 | 2.296 | 2.216 | -8.89% | 10.052 | 68.87% |
| validation | 5616 | 46 | 20 | 16.61% | 22.87% | -9.24% | 1.023 | 1.469 | 0.993 | -16.73% | 4.354 | 87.75% |
| best_available_oos | 5570 | 92 | 30 | 15.34% | 12.05% | -3.70% | 1.124 | 1.670 | 1.420 | -10.81% | 2.885 | 66.82% |
| full | 14631 | 169 | 60 | 16.39% | 15.51% | -2.96% | 1.113 | 1.612 | 0.872 | -18.80% | 3.521 | 77.95% |

## Trade quality

| Partition | Mean net | Median net | Win rate | Worst | Mean SPY | Mean excess | Excess t | Excess CI | Drop-best-5 | Avg hold |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| train | 32.59% | 19.95% | 50.00% | -8.62% | 17.24% | 15.34% | 1.79 | [0.17, 32.56] | 8.45% | 241.00 |
| validation | 13.47% | -3.37% | 45.65% | -8.18% | 22.03% | -8.56% | -1.61 | [-17.73, 2.79] | 3.84% | 156.09 |
| best_available_oos | 8.23% | -6.67% | 45.65% | -16.53% | 9.96% | -1.72% | -0.71 | [-6.18, 3.26] | 3.49% | 82.29 |
| full | 11.30% | -8.18% | 43.20% | -16.53% | 12.80% | -1.50% | -0.68 | [-5.52, 2.93] | 7.51% | 116.21 |

## Cost stress

| Partition | 1x CAGR | 2x | 5x | 10x |
|---|---:|---:|---:|---:|
| train | 19.71% | 19.54% | 19.05% | 18.29% |
| validation | 16.61% | 16.27% | 15.36% | 13.79% |
| best_available_oos | 15.34% | 14.91% | 14.35% | 12.17% |
| full | 16.39% | 16.00% | 15.17% | 13.39% |

## Full-period calendar years

| Year | Portfolio | SPY | Exposure-matched excess | Exposure |
|---|---:|---:|---:|---:|
| 2016 | 12.54% | 8.43% | 4.07% | 99.48% |
| 2017 | 38.56% | 21.71% | 14.02% | 99.99% |
| 2018 | -11.21% | -4.57% | -2.38% | 43.25% |
| 2019 | 27.77% | 31.22% | -3.61% | 99.89% |
| 2020 | 17.50% | 18.33% | -15.79% | 93.92% |
| 2021 | 15.06% | 28.73% | -6.97% | 91.65% |
| 2022 | 10.36% | -18.18% | 2.68% | 41.72% |
| 2023 | 11.63% | 26.18% | -3.20% | 42.85% |
| 2024 | 15.14% | 24.89% | -8.78% | 97.17% |
| 2025 | 13.59% | 17.72% | -13.20% | 73.40% |
| 2026 | 17.85% | 10.09% | 7.68% | 91.06% |

## Statistical and robustness diagnostics

- Daily-return t-statistic: 3.514.
- Effective sample size: 2511.0.
- PSR versus zero: 99.97%.
- Approximate DSR probability across 573 declared trials: 66.08%.
- Block-bootstrap CAGR 90% interval: 8.40% to 24.84%.
- Monte Carlo MDD 90% interval: -34.10% to -14.48%.
- Positive months: 54.17%.

## Bias assessment

| Risk | Assessment | Evidence |
|---|---|---|
| Lookahead | Absent in implementation | Close-confirmed signal; next-ticker-open entry; period exit executes at the first known outside-window open. |
| Survivorship | Unresolved | PIT membership is enforced, but coverage is incomplete and some former/delisted members have no bars. |
| Data snooping | Present | Slope10, exact calendar endpoints and forced period exit were specified after prior validation inspection. |
| Transaction costs | Included | 5 bps commission plus 5 bps slippage each way at 1x; 2x/5x/10x stress reported. |
| Liquidity | Partially controlled | Existing ADV capacity constraints are retained; missing histories remain a limitation. |
| Untouched OOS | Absent | Every available chronological partition is contaminated for this newly combined specification. |

## Interpretation

This run measures the current configuration but cannot validate it. The 10-session slope was selected after a train grid and failed validation; the exact calendar and forced boundary exit are also post-hoc. Give primary weight to exposure-matched excess, outlier trims, cost stress and the absence of untouched OOS, not raw CAGR.

## Reproduction

```bash
.venv/bin/python scripts/current_ma60_candidate_backtest.py --price-csv SP500_PIT_2016_2026.csv --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json --membership-csv scripts/data/sp500_membership.csv --sector-json scripts/data/sp500_constituents.json --output-dir backtests/current_ma60_candidate_v2/results --iterations 1000
```
