# Backtest Verification Report — Existing-Data Exploratory Replay

Generated: 2026-08-01T20:30:09

## Backtest Score

**Raw score ignoring the survivorship cap: 25/100.**  
**Rubric score after the unresolved-survivorship hard cap: 20/100 — Reject.**

| Component | Score | Max |
|---|---:|---:|
| A. Statistical validity | 7 | 30 |
| B. Risk-adjusted performance | 7 | 25 |
| C. Robustness / later-data evidence | 8 | 25 |
| D. Trade quality / consistency | 3 | 20 |
| **Raw total** | **25** | **100** |

## Executive summary

The frozen Trial 288 replay produced 89 trades, 0.05% net CAGR, 0.031 Sharpe, 1.059 profit factor and -6.81% MDD. It fails the 20% CAGR requirement even before applying any survivorship cap.

The result is exploratory, not untouched OOS. A benchmark date-alignment defect was corrected before opening 2022–2026 outcomes; the old Trial 288 coefficients are invalidated, while its rule and frozen fit/calibration chronology are unchanged.

## Performance and significance

| Metric | Value | Status |
|---|---:|---|
| Net CAGR | 0.05% | FAIL vs 20% |
| Total return | 0.19% | Weak |
| Trades | 89 | Pass 30-trade count only |
| Sharpe / Sortino / Calmar | 0.031 / 0.045 / 0.007 | Fail |
| MDD / duration | -6.81% / 497 days | Magnitude low, recovery poor |
| PF / expectancy | 1.059 / 0.206% | Fail PF |
| Win rate / payoff | 42.7% / 1.422 | Marginal |
| t-stat / PSR | 0.063 / 52.5% | Not significant |
| DSR probability (>=289 trials) | 0.22% | Fail |
| Ljung–Box(10) p-value | 0.0053 | Serial dependence present if <0.05 |
| Positive months / quarters | 39.6% / 37.5% | Fail |

## Robustness

Drop-top-five expectancy is -1.71% (PF 0.536); drop-top-ten expectancy is -2.59% (PF 0.339). The positive headline expectancy is outlier-dependent.

Block-bootstrap CAGR 5th/median/95th percentiles are -2.61% / 0.11% / 2.83%. Trade-bootstrap probability of nonpositive expectancy is 43.2%.

### Cost stress

| Costs | Trades | CAGR | PF | MDD |
|---|---:|---:|---:|---:|
| 1x | 89 | 0.05% | 1.059 | -6.81% |
| 2x | 90 | -0.11% | 1.144 | -7.03% |
| 5x | 93 | -1.18% | 0.937 | -7.60% |
| 10x | 94 | -2.05% | 0.715 | -9.17% |

### Chronological folds

| Fold | CAGR | Sharpe | MDD | Positive months |
|---|---:|---:|---:|---:|
| 2022-01-01…2023-12-31 | 1.15% | 0.467 | -3.10% | 42.9% |
| 2024-01-01…2026-03-31 | -0.80% | -0.184 | -6.81% | 37.0% |

Across all prespecified neighbouring threshold cells, CAGR ranges from -0.92% to 0.87%; every cell has negative drop-top-five expectancy. Parameter sensitivity is saved separately and is diagnostic only; no neighbouring cell replaces the frozen p85/p50 primary result.

## Bias assessment

| Bias | Status | Evidence |
|---|---|---|
| Lookahead | Absent after correction | Historical SPY is date-aligned at or before the stock as-of date; regression-tested. Signal date precedes every fill. |
| Survivorship | Present / unresolved | Existing PIT reconstruction has 91.31% member-day coverage, not complete delisted coverage. |
| Data snooping | Present as multiplicity risk | This is a later-data replay of a selected candidate after at least 288 earlier trials; DSR fails. |
| Costs | Included and stressed | 5 bps commission + 5 bps slippage per side at baseline; 2x/5x/10x reported. |
| Asset / leverage | Absent | Individual stocks only, no SPY trades and no leverage or sizing changes. |

## Verdict

**25/100 before the requested cap waiver; 20/100 under the rubric. Reject.** The later existing data does not rescue Trial 288: net CAGR is 0.05%, statistical confidence is absent, and removing the largest winners turns expectancy negative. The original goal is not complete.
