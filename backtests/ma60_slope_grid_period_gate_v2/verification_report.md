# Trial 569–572 Verification — MA60 Slope-Window Grid

## Verdict

**VALIDATION_FAIL / DESCRIPTIVE_ONLY.** The 10-session slope window beat the
20/30/40-session alternatives on the frozen train objective, but it failed two
validation gates. Best-available OOS remained sealed.

The calendar dates remain potentially post-hoc, so this grid cannot establish
a deployable improvement even if a slope passes chronological gates.

## Frozen family

Only the MA60 slope comparison interval changes: 10, 20, 30 or 40 aligned
common trading sessions. The stock must close above SMA60, its SMA60 slope
must be positive and strictly above SPY's SMA60 slope, and the condition must
change from false to true. Signal confirmation, next-open fill, PIT membership,
user-supplied fill-date calendar, 8% initial stop, +3R arm, 24% trail, no
timeout, costs, sizing and portfolio limits are unchanged.

All four cells count. Declared multiplicity rises from 567 to 571.

## Train grid

| Slope window | Trades | Armed | CAGR | Excess CAGR | Sharpe | MDD | PF | Drop-best-five | Gate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 10 | 18 | 9 | **19.21%** | **+7.44%** | **1.362** | -9.35% | 8.679 | +4.70% | PASS / SELECTED |
| 20 | 16 | 9 | 13.56% | +2.66% | 1.078 | -12.54% | 8.704 | +4.44% | PASS |
| 30 | 20 | 10 | 11.25% | +0.45% | 0.938 | -10.72% | 4.783 | +1.24% | PASS |
| 40 | 21 | 9 | 9.85% | -1.26% | 0.858 | -10.43% | 3.907 | -0.32% | FAIL |

The surface degrades monotonically from 10 to 40 sessions on train, but every
cell has only 16–21 completed trades. For the selected 10-session cell, mean
matched-SPY excess was +14.37%, yet its bootstrap 95% CI [-3.39%, +35.35%]
included zero. The apparent train lead is therefore thin and uncertain.

## Validation failure

The selected 10-session slope completed 44 validation trades:

| Metric | Validation result | Frozen requirement |
|---|---:|---:|
| CAGR | 13.53% | >0: pass |
| Exposure-matched excess CAGR | **-6.93%** | >0: fail |
| MDD | -28.86% | >-30%: pass |
| Profit factor | 3.715 | >1.2: pass |
| Drop-best-five expectancy | **-1.08%** | >0: fail |
| Trades | 44 | >=30: pass |

Mean validation net trade return was +12.31%, but matched SPY returned +18.81%
over the same holding windows. Mean excess was -6.50%; only 15.91% of trades
beat SPY. The wide bootstrap CI [-19.53%, +13.67%] does not establish a stable
effect. Calendar-year exposure-matched returns were negative in 2019, 2020 and
2021; only the short 2022 accounting tail was positive.

The 10-session slope improves descriptive validation raw CAGR versus the
20-session incumbent (13.53% versus 8.34%), MDD (-28.86% versus -31.59%) and
excess-CAGR level (-6.93% versus -10.39%). It still fails the prespecified
positive-excess and outlier-robustness requirements. Choosing it on those
relative improvements would relax the frozen gates after seeing validation.

## Score and bias assessment

The train cell's measured A/B/C/D score is 66/83, normalized to 80/100. Hard
caps apply for unresolved survivorship/incomplete delisted coverage (20), no
valid OOS/WFA (55), and fewer than 30 completed train trades (40). Final
**Backtest Score: 20/100 — Reject**.

The exact calendar schedule has no demonstrated real-time generation rule,
only seven of its 18 windows are executable, and all available partitions are
research-contaminated. These limitations dominate the attractive train score.

## Reproduction

```bash
.venv/bin/python scripts/ma60_slope_grid_period_gate_experiment.py \
  --price-csv SP500_PIT_2016_2026.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --membership-csv scripts/data/sp500_membership.csv \
  --sector-json scripts/data/sp500_constituents.json \
  --incumbent-json backtests/ma60_period_gate_v2/results/ma60_period_gate_2026-08-02_172922.json \
  --output-dir backtests/ma60_slope_grid_period_gate_v2/results \
  --iterations 1000

.venv/bin/python -m pytest \
  tests/test_ma60_slope_grid_period_gate_experiment.py \
  tests/test_ma60_period_gate_experiment.py \
  tests/test_portfolio_backtest.py -q
.venv/bin/python -m pytest tests/ -q
.venv/bin/python -m py_compile \
  scripts/ma60_slope_grid_period_gate_experiment.py
git diff --check
```

The JSON, Markdown, four train signal/trade/equity triplets, and selected
validation triplet are under
`backtests/ma60_slope_grid_period_gate_v2/results/`. No OOS artifact exists
because validation failed.
