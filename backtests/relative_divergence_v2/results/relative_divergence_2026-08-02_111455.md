# Trial 505–518 — Positive Relative-Strength Divergence Gate

Final verdict: **INCONCLUSIVE**

> The confirmatory family failed its outcome-free 30-activation train gate (24/34). Return tables below are the separately frozen Trial 519 descriptive audit and cannot support an `IMPROVES` verdict.

Validation accessed: **YES**
Best-available OOS accessed: **YES**

## Backtest Score: 14/100 — Reject

| Component | Score | Available max |
|---|---:|---:|
| A. Statistical validity | 7 | 30 |
| B. Risk-adjusted performance | 5 | 25 |
| C. Robustness computable | 0 | 8 |
| D. Trade quality / consistency | 0 | 20 |
| Measured total | 12 | 83 |
| Normalized raw score | 14 | 100 |
| Caps | unresolved survivorship → 20; no genuine untouched OOS/WFA → 55 | |
| **Final score** | **14** | **100** |

The score is the repository analyst's capped diagnostic for the primary best-available OOS cell. It remains non-qualifying because the data has incomplete delisted coverage and no genuinely untouched OOS.

## Every portfolio variant by chronological fold

| Fold | Variant | Signals | Trades | Net CAGR | Sharpe | Sortino | Excess CAGR | MDD | Exposure | Mean trade excess | PF |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| train | baseline | 34 | 32 | 1.60% | 0.631 | 0.835 | -0.23% | -4.13% | 13.4% | -0.73% | 1.627 |
| train | primary_20d_0pp | 24 | 23 | 0.75% | 0.439 | 0.621 | -0.47% | -2.05% | 8.0% | -1.60% | 1.330 |
| train | negative_control | 10 | 9 | 0.81% | 0.494 | 0.601 | 0.21% | -3.56% | 5.4% | 1.50% | 2.922 |
| train | lookback_5d | 8 | 8 | 0.92% | 0.837 | 1.213 | 0.37% | -1.61% | 3.7% | 2.60% | 3.381 |
| train | lookback_10d | 9 | 7 | -0.79% | -0.950 | -1.140 | -1.00% | -1.88% | 1.7% | -7.07% | 0.000 |
| train | lookback_40d | 23 | 22 | 2.08% | 1.079 | 1.609 | 0.71% | -1.55% | 10.0% | -0.45% | 1.862 |
| train | lookback_60d | 24 | 22 | 0.74% | 0.330 | 0.419 | -0.38% | -4.17% | 9.6% | -1.00% | 1.323 |
| train | threshold_2pp | 14 | 14 | 0.84% | 0.615 | 0.921 | 0.08% | -1.36% | 5.7% | -2.09% | 1.203 |
| train | threshold_5pp | 5 | 5 | 0.32% | 0.458 | 0.752 | 0.11% | -0.44% | 1.5% | 1.25% | 2.160 |
| validation | baseline | 105 | 86 | 1.14% | 0.277 | 0.391 | 0.26% | -9.38% | 17.3% | -0.09% | 1.352 |
| validation | primary_20d_0pp | 75 | 64 | 2.52% | 0.602 | 0.856 | 1.26% | -7.74% | 14.4% | 1.08% | 1.743 |
| validation | negative_control | 30 | 27 | 0.18% | 0.090 | 0.133 | -0.21% | -3.04% | 7.5% | -0.78% | 1.008 |
| validation | lookback_5d | 30 | 29 | -0.65% | -0.214 | -0.281 | 0.39% | -5.87% | 7.6% | 2.56% | 1.403 |
| validation | lookback_10d | 40 | 37 | 3.56% | 0.963 | 1.578 | 1.81% | -3.33% | 11.0% | 1.72% | 2.247 |
| validation | lookback_40d | 75 | 64 | 1.71% | 0.433 | 0.621 | 1.01% | -6.94% | 13.8% | -0.07% | 1.362 |
| validation | lookback_60d | 65 | 54 | 1.15% | 0.305 | 0.413 | 0.68% | -6.53% | 11.8% | 0.36% | 1.493 |
| validation | threshold_2pp | 60 | 53 | 3.36% | 0.698 | 1.026 | 2.18% | -6.96% | 13.4% | 1.38% | 1.852 |
| validation | threshold_5pp | 43 | 39 | 2.87% | 0.615 | 0.926 | 1.93% | -6.42% | 10.5% | 1.79% | 1.780 |
| best_available_oos | baseline | 173 | 131 | -3.22% | -0.766 | -0.978 | -4.31% | -15.96% | 17.5% | -2.78% | 0.628 |
| best_available_oos | primary_20d_0pp | 122 | 101 | -2.16% | -0.566 | -0.728 | -3.18% | -12.03% | 15.0% | -3.00% | 0.586 |
| best_available_oos | negative_control | 51 | 46 | -0.76% | -0.281 | -0.399 | -1.63% | -6.50% | 7.4% | -1.74% | 1.004 |
| best_available_oos | lookback_5d | 47 | 41 | -0.17% | -0.064 | -0.087 | -0.62% | -3.77% | 7.9% | -0.29% | 1.211 |
| best_available_oos | lookback_10d | 68 | 59 | -1.55% | -0.569 | -0.732 | -2.16% | -7.48% | 9.5% | -2.67% | 0.597 |
| best_available_oos | lookback_40d | 119 | 91 | -3.97% | -1.085 | -1.364 | -4.29% | -18.25% | 14.6% | -3.18% | 0.475 |
| best_available_oos | lookback_60d | 120 | 93 | -2.65% | -0.739 | -0.937 | -3.70% | -13.52% | 14.3% | -3.33% | 0.558 |
| best_available_oos | threshold_2pp | 87 | 73 | -1.52% | -0.430 | -0.554 | -2.55% | -9.24% | 12.0% | -2.88% | 0.632 |
| best_available_oos | threshold_5pp | 59 | 49 | -0.69% | -0.214 | -0.277 | -1.23% | -6.00% | 9.3% | -1.72% | 0.800 |

## Prespecified primary comparison by fold

| Fold | Retained signals | CAGR lift | Exposure-matched excess CAGR lift | Pass-minus-fail mean excess | MDD change | Divergence/excess Spearman |
|---|---:|---:|---:|---:|---:|---:|
| train | 70.6% | -0.85 pp | -0.24 pp | -3.10 pp | 2.08 pp | -0.106 |
| validation | 71.4% | 1.38 pp | 1.00 pp | 1.86 pp | 1.64 pp | 0.099 |
| best_available_oos | 70.5% | 1.06 pp | 1.13 pp | -1.26 pp | 3.93 pp | -0.079 |

## Primary trade-level evidence

| Fold | Cohort | Trades | Mean gross | Mean net | Median net | Win rate | Mean matched excess | Excess 95% CI | Clustered t | Drop-best-5 mean |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| train | baseline | 32 | 2.22% | 2.01% | 0.75% | 50.0% | -0.73% | [-3.77, 2.47] | -0.39 | -1.24% |
| train | qualifying | 23 | 1.40% | 1.20% | -2.51% | 43.5% | -1.60% | [-5.32, 2.36] | -0.70 | -3.27% |
| train | rejected | 9 | 4.30% | 4.09% | 6.24% | 66.7% | 1.50% | [-3.28, 6.30] | 0.54 | -4.05% |
| validation | baseline | 86 | 1.70% | 1.50% | -4.69% | 39.5% | -0.09% | [-2.25, 2.27] | -0.08 | -0.47% |
| validation | qualifying | 61 | 2.58% | 2.37% | -4.78% | 42.6% | 0.39% | [-2.07, 3.00] | 0.30 | -0.33% |
| validation | rejected | 25 | -0.43% | -0.63% | -4.59% | 32.0% | -1.26% | [-5.22, 3.69] | -0.63 | -5.02% |
| best_available_oos | baseline | 131 | -1.59% | -1.78% | -5.53% | 28.2% | -2.78% | [-4.25, -1.23] | -3.66 | -2.94% |
| best_available_oos | qualifying | 90 | -2.46% | -2.66% | -6.24% | 24.4% | -3.39% | [-4.93, -1.73] | -4.43 | -4.13% |
| best_available_oos | rejected | 41 | 0.33% | 0.13% | -3.18% | 36.6% | -1.45% | [-4.66, 1.86] | -0.75 | -3.10% |

## Primary year-by-year portfolio evidence

| Fold | Year | Baseline return | Primary return | Baseline excess | Primary excess | Primary exposure |
|---|---:|---:|---:|---:|---:|---:|
| train | 2016 | 0.28% | -0.60% | -0.30% | -1.01% | 9.1% |
| train | 2017 | 1.54% | -0.35% | -1.24% | -2.00% | 8.6% |
| train | 2018 | 1.72% | 2.65% | 1.05% | 2.03% | 7.3% |
| validation | 2019 | 2.62% | 3.52% | -0.05% | 1.17% | 16.4% |
| validation | 2020 | -3.74% | -2.10% | -0.50% | 0.31% | 10.6% |
| validation | 2021 | 6.70% | 7.42% | 0.75% | 2.00% | 18.5% |
| validation | 2022 | -1.67% | -0.77% | 0.62% | 0.43% | 6.6% |
| best_available_oos | 2022 | -4.46% | -3.67% | -0.18% | -0.28% | 13.1% |
| best_available_oos | 2023 | -4.84% | -1.31% | -7.08% | -4.39% | 13.9% |
| best_available_oos | 2024 | 0.06% | -2.10% | -4.48% | -6.08% | 20.1% |
| best_available_oos | 2025 | -4.51% | -2.16% | -6.25% | -2.15% | 13.5% |
| best_available_oos | 2026 | -0.29% | -0.21% | -0.77% | -0.95% | 13.5% |

## Missing observations and PIT exclusions

| Fold | Available divergence | Positive | Negative control | Missing | PIT detection drops | Signal-date drops | Fill-date drops |
|---|---:|---:|---:|---:|---:|---:|---:|
| train | 34 | 24 | 10 | 0 | 16 | 0 | 0 |
| validation | 105 | 75 | 30 | 0 | 34 | 0 | 0 |
| best_available_oos | 173 | 122 | 51 | 0 | 36 | 0 | 0 |

## Sequential gate and robustness interpretation

Train gate: **FAIL**

- FAIL — primary_executed_trades>=30
- FAIL — net_cagr_lift>0
- FAIL — exposure_matched_excess_cagr_lift>0
- FAIL — qualifying_minus_rejected_mean_excess>0
- FAIL — drop_best_five_expectancy>0

- Best-available OOS primary mean excess was -3.00% (bootstrap 95% CI [-4.53, -1.29]).
- OOS drop-best-five net expectancy was -3.49%; winsorized expectancy was -2.39%.
- At 2×, 5× and 10× costs, both baseline and primary remained negative in OOS; the gate did not create positive economic performance.
- Divergence quartiles were not monotonic and the OOS Spearman association was weakly negative.

### Best-available OOS primary portfolio detail

| Total return | Annual volatility | Calmar | Average positions | Slot utilization | Turnover | Estimated costs | Capacity rejects | Cash/sector/liquidity rejects |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| -9.13% | 3.73% | -0.180 | 2.88 | 28.8% | 10.17x | $954.64 | 5 | 16 |

### Best-available OOS regime cohorts

| Regime | Qualifying trades | Rejected trades | Qualifying mean excess | Rejected mean excess | Difference |
|---|---:|---:|---:|---:|---:|
| spy_above_sma200 | 67 | 38 | -3.89% | -1.10% | -2.79 pp |
| spy_below_sma200 | 23 | 3 | -1.93% | -5.90% | 3.97 pp |
| high_volatility | 48 | 18 | -2.98% | -3.34% | 0.36 pp |
| low_volatility | 42 | 23 | -3.86% | 0.02% | -3.88 pp |
| breadth_ge_50 | 66 | 34 | -3.58% | -0.41% | -3.16 pp |
| breadth_lt_50 | 24 | 7 | -2.87% | -6.51% | 3.63 pp |
| edge_rank_ge_70 | 35 | 12 | -3.44% | -5.90% | 2.46 pp |
| edge_rank_lt_70 | 55 | 29 | -3.36% | 0.38% | -3.74 pp |

## Interpretation

The prespecified family failed its outcome-free activation gate. All return results are a post-density descriptive audit and cannot support IMPROVES, regardless of their direction.

The 5/10/40/60-session and 2/5pp cells are sensitivity/multiple comparisons. They cannot replace the frozen 20-session, zero-threshold primary result. Ranking was not run because it cannot be separated from fixed Edge Rank sizing in the current engine.

The apparent portfolio lift in validation and best-available OOS came with lower exposure. In best-available OOS, qualifying baseline trades had worse matched-window excess than rejected trades, while both baseline and challenger lost money. That mixed evidence is neither reliable stock-selection alpha nor economically successful.

## Reproduction

```bash
.venv/bin/python scripts/relative_divergence_experiment.py backtests/exploratory_existing_data_replay/detections_date_aligned/vcp_backtest_2026-08-01_202358.json --price-csv SP500_PIT_2016_2026.csv --membership-csv scripts/data/sp500_membership.csv --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json --breadth-csv scripts/data/sp500_breadth_daily.csv --output-dir backtests/relative_divergence_v2/results --iterations 1000 --descriptive-full-audit
```
