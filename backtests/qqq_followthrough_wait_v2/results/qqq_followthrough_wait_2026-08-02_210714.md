# QQQ Risk-On Follow-Through Wait Experiment

Classification: **DESCRIPTIVE_ONLY — validation/OOS already contaminated**

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

The experiment skips the first N complete SPY/QQQ-aligned sessions after each QQQ risk-on fill. Only fresh MA60/Slope10 false-to-true orders after the embargo can enter; embargoed orders are never carried forward.

## Train-only wait grid

| Wait | Signals | Trades | CAGR | Excess CAGR | Sharpe | MDD | PF | Stop rate | Large-cohort stop rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2 | 3002 | 18 | 20.08% | 8.93% | 1.598 | -8.89% | 10.098 | 38.89% | 37.50% |
| 3 | 3002 | 18 | 20.08% | 8.93% | 1.598 | -8.89% | 10.098 | 38.89% | 37.50% |
| 4 | 3002 | 18 | 20.08% | 8.93% | 1.598 | -8.89% | 10.098 | 38.89% | 37.50% |
| 5 | 3002 | 18 | 20.08% | 8.93% | 1.598 | -8.89% | 10.098 | 38.89% | 37.50% |

Train could **not identify this parameter**: waits 2/3/4/5 produced exactly the same signals and portfolio because no new QQQ risk-on transition occurred inside train. **2 sessions** is only the prespecified lower-wait tie-break, not an evidence-backed winner. The tie-break was frozen before validation and best-available OOS evaluation.

## Frozen selected wait versus zero-wait control

| Partition | Variant | Trades | CAGR | SPY CAGR | Excess CAGR | Sharpe | MDD | PF | Stop rate | Clustered-stop share |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| train | wait 0 | 18 | 20.08% | 9.70% | 8.93% | 1.598 | -8.89% | 10.098 | 38.89% | 42.86% |
| train | wait 2 | 18 | 20.08% | 9.70% | 8.93% | 1.598 | -8.89% | 10.098 | 38.89% | 42.86% |
| validation | wait 0 | 46 | 18.97% | 22.87% | -8.23% | 1.149 | -16.73% | 4.988 | 45.65% | 61.90% |
| validation | wait 2 | 41 | 21.83% | 22.87% | -6.03% | 1.397 | -13.91% | 6.673 | 41.46% | 64.71% |
| best_available_oos | wait 0 | 91 | 15.66% | 12.05% | -3.14% | 1.147 | -10.81% | 2.962 | 49.45% | 51.11% |
| best_available_oos | wait 2 | 89 | 9.25% | 12.05% | -7.81% | 0.775 | -13.16% | 2.452 | 49.44% | 43.18% |
| full | wait 0 | 168 | 17.33% | 15.51% | -2.07% | 1.173 | -18.16% | 3.729 | 51.19% | 59.30% |
| full | wait 2 | 162 | 15.29% | 15.51% | -3.19% | 1.111 | -18.61% | 3.700 | 50.62% | 53.66% |

## Selected-wait OOS cost stress

| Costs | CAGR | MDD | Sharpe | PF |
|---:|---:|---:|---:|---:|
| 1x | 9.25% | -13.16% | 0.775 | 2.452 |
| 2x | 8.87% | -13.44% | 0.748 | 2.368 |
| 5x | 8.27% | -13.65% | 0.718 | 2.178 |
| 10x | 6.69% | -16.11% | 0.598 | 2.008 |

## Verdict

INCONCLUSIVE / DO NOT ADOPT: train contains no QQQ risk-on transition, so it cannot distinguish waits 2-5. The mechanical two-session tie-break improves validation but materially worsens best-available OOS and full-sample performance.

The QQQ dates and MA60/Slope10 specification were already inspected through the available sample. These results are not untouched OOS evidence and cannot validate a live edge.

## Reproduction

```bash
.venv/bin/python scripts/qqq_followthrough_wait_experiment.py --price-csv SP500_PIT_2016_2026.csv --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json --membership-csv scripts/data/sp500_membership.csv --sector-json scripts/data/sp500_constituents.json --output-dir backtests/qqq_followthrough_wait_v2/results --iterations 1000
```
