# Backtest Verification Report — Down-Close Pivot-Hold v2

Generated 2026-08-01. Trial 206 was declared before implementation/results.

## Verdict: REJECT — 31/100; untouched OOS remains sealed

The candidate passed its train gate but failed independently on validation.
Net validation CAGR was **0.11%**, far below 20%, and the preliminary
backtest-analyst score was **31/100**, far below the required >80.

| Metric | Train 2016-07 to 2021 | Validation 2022 to 2026-06 |
|---|---:|---:|
| Trades | 55 | 92 |
| Net CAGR | 2.39% | 0.11% |
| Sharpe | 0.655 | 0.048 |
| Sortino | 1.034 | 0.068 |
| Calmar | 0.331 | 0.015 |
| MDD | -7.22% | -7.48% |
| Profit factor | 1.850 | 1.147 |
| Expectancy / trade | 3.35% | 0.77% |
| Drop-top-5 expectancy | 0.43% | -2.09% |
| PSR vs zero | 93.85% | 53.96% |
| Approximate DSR (206 trials) | 8.88% | 0.37% |

Validation t-statistic was 0.10. Block-bootstrap CAGR 5th/median/95th
percentiles were -3.00% / 0.13% / 3.59%; Monte Carlo final-equity percentiles
were 0.861 / 1.005 / 1.168. Positive months and quarters were 45.3% and 44.4%.
Train-to-validation Sharpe efficiency was 0.073 in the scoring comparison.

## Robustness checks

| Validation cell | Trades | Net CAGR | Sharpe | PF |
|---|---:|---:|---:|---:|
| Primary 10 sessions, 1x costs | 92 | 0.11% | 0.048 | 1.147 |
| 5-session sensitivity | 91 | 0.12% | 0.050 | 1.207 |
| 15-session sensitivity | 92 | 0.11% | 0.048 | 1.147 |
| 2x costs | 95 | -0.04% | 0.012 | 1.156 |
| 5x costs | 94 | -0.52% | -0.099 | 1.059 |
| 10x costs | 92 | -1.79% | -0.403 | 0.853 |

The flat 10/15-session result and nearly identical 5-session result show that
the rejection is not a boundary artefact. Returns are dependent on a few large
winners and do not survive even modest cost stress.

## Integrity and data audit

- Signals use only completed closes; fills occur at the following open.
- `forward_outcome` is ignored and covered by unit tests.
- Portfolio capital, Edge sizing, maximum holdings, stops, time exit, costs,
  cash, ADV and sector constraints are unchanged; no leverage is used.
- Holdings are point-in-time S&P 500 stocks only. SPY is benchmark-only.
- PIT member-day coverage is 91.31% (599/720 symbols retained); 42 train and
  28 validation detections outside membership intervals were excluded.
- Validation had 92 trades, so the failure is not a small-sample hard cap.
- Sealed 2000-2005 OOS was not opened because every validation gate except
  trade count failed.

Machine-readable report and daily/trade CSVs:
`results/down_close_pivot_hold_baseline_validation_2026-08-01_123934.json`,
`results/down_close_pivot_hold_baseline_*_daily.csv`, and
`results/down_close_pivot_hold_baseline_*_trades.csv`.
