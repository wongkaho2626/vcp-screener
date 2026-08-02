# Trial 569–572 — MA60 Slope-Window Grid

Sequential outcome: **VALIDATION_FAIL**
Evidence classification: **DESCRIPTIVE_ONLY**

## Backtest Score: 20/100 — Reject

| Component | Score | Available max |
|---|---:|---:|
| A. Statistical validity | 20 | 30 |
| B. Risk-adjusted performance | 20 | 25 |
| C. Robustness computable | 8 | 8 |
| D. Trade quality / consistency | 18 | 20 |
| Measured total | 66 | 83 |
| Normalized raw score | 80 | 100 |
| Caps applied | unresolved survivorship bias / incomplete delisted coverage → 20; no formal out-of-sample or walk-forward segment → 55; fewer than 30 completed train trades → 40 | |
| **Final score** | **20** | **100** |

MA60, the user-supplied fill-date calendar and the 8% / +3R / 24% no-timeout exit remain unchanged. Only the 10/20/30/40-session slope window changes.

## Train grid

| Slope | Signals | Trades | Armed | CAGR | Excess CAGR | Sharpe | Sortino | Calmar | MDD | PF | Drop-best-5 | Gate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 10 | 3003 | 18 | 9 | 19.21% | 7.44% | 1.362 | 1.989 | 2.058 | -9.35% | 8.679 | 4.70% | PASS |
| 20 | 2852 | 16 | 9 | 13.56% | 2.66% | 1.078 | 1.519 | 1.083 | -12.54% | 8.704 | 4.44% | PASS |
| 30 | 2804 | 20 | 10 | 11.25% | 0.45% | 0.938 | 1.294 | 1.052 | -10.72% | 4.783 | 1.24% | PASS |
| 40 | 2805 | 21 | 9 | 9.85% | -1.26% | 0.858 | 1.186 | 0.947 | -10.43% | 3.907 | -0.32% | FAIL |

## Sequential access

Train-qualified slopes: **[10, 20, 30]**.
Selected slope: **10 sessions**.
Validation accessed: **YES**.
Best-available OOS accessed: **NO**.

### Validation

Slope 10: 44 trades, 13.53% CAGR, -6.93% exposure-matched excess CAGR, -28.86% MDD, drop-best-five -1.08%.

## Interpretation

The 10-session slope won train but failed the frozen validation gate, so OOS remained sealed.

The exact calendar dates remain potentially post-hoc. A passing slope cannot convert this family into valid untouched OOS evidence.

## Reproduction

```bash
.venv/bin/python scripts/ma60_slope_grid_period_gate_experiment.py --price-csv SP500_PIT_2016_2026.csv --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json --membership-csv scripts/data/sp500_membership.csv --sector-json scripts/data/sp500_constituents.json --incumbent-json backtests/ma60_period_gate_v2/results/ma60_period_gate_2026-08-02_172922.json --output-dir backtests/ma60_slope_grid_period_gate_v2/results --iterations 1000
```
