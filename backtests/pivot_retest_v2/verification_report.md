# Backtest Verification Report — pivot-retest v2

Evaluated 2026-08-01 from the pre-result `frozen_spec.md`. The sealed
2000-2005 OOS was **not opened** because the validation gate failed.

## Backtest Score: 41 / 100 — Weak (validation-only preliminary score)

| Component | Score | Max |
|---|---:|---:|
| A. Statistical Validity & Significance | 7 | 30 |
| B. Risk-Adjusted Performance | 7 | 25 |
| C. Robustness & Validation | 18 | 25 |
| D. Trade Quality & Consistency | 9 | 20 |
| **Raw / final** | **41 / 41** | **100** |
| Caps | none on the measured PIT validation; final OOS score unavailable | |

This score is deliberately not a final strategy score: the spec required
validation CAGR >=20% and preliminary score >80 before opening untouched OOS.
Both failed, so the final-score claim cannot be made.

## Executive summary

The structural pivot-retest entry improves materially on the frozen MA20
pullback baseline in 2022-2026, but remains economically far below the goal.
It executes 58 validation trades, earns net CAGR **0.91%**, Sharpe **0.320**,
PF **1.39**, and MDD **-4.17%**. The mean is statistically weak (t **0.67**,
PSR **74.9%**, approximate DSR **1.1%** at 195 declared trials), the bootstrap
CAGR interval crosses zero, and dropping the five largest winners turns
expectancy negative. Result: Reject; OOS remains sealed.

## 1. Performance metrics

| Metric | Train 2016H2-2021 | Validation 2022-2026 | Gate |
|---|---:|---:|---|
| Trades | 34 | 58 | validation >=30: pass |
| Net CAGR | 1.77% | **0.91%** | >=20%: **fail** |
| Total return | 9.98% | 4.04% | context |
| Sharpe | 0.627 | 0.320 | positive, weak |
| Sortino | 1.105 | 0.484 | weak |
| Calmar | 0.606 | 0.219 | weak |
| MDD | -2.91% | -4.17% | low due to sparse exposure |
| Profit factor | 2.10 | 1.39 | validation >1.2: pass |
| Expectancy / trade | +3.88% | +1.70% | positive, outlier-driven |
| Win rate / payoff | 52.9% / 1.87 | 36.2% / 2.44 | coherent |
| Frozen MA20 baseline CAGR | 0.48% | -2.49% | pivot retest is better, not sufficient |
| Frozen MA20 baseline Sharpe | 0.183 | -0.689 | context |

## 2. Statistical significance

- Validation daily t = **0.668**; effective sample size 970.
- PSR versus zero = **74.94%**; approximate DSR probability at 195 trials =
  **1.11%** (benchmark Sharpe 1.406).
- Block-bootstrap validation CAGR 90% interval = **-1.58% to +3.50%**;
  median +0.96%. It includes zero comfortably.
- Validation positive months = **47.2%**, positive quarters = **50.0%**.
- Train/validation Sharpe efficiency = 0.320 / 0.627 = **0.51**. The effect
  retains sign but not economic magnitude.

## 3. Bias assessment

| Bias | Status | Evidence |
|---|---|---|
| Lookahead | Absent | Breakout and pivot retest are walked from `as_of_date`; `forward_outcome` is ignored; next-open fill is unit-tested. |
| Survivorship | Mitigated above declared threshold | PIT union 720, kept 599 plus real SPY benchmark, 91.31% member-day coverage; membership gate dropped 42 train and 28 validation non-member detections. |
| Data snooping | Penalised | Rule and gate frozen before implementation/results; DSR uses 195 trials. |
| Costs | Addressed | 5 bps commission + 5 bps slippage per side; 2x/5x/10x stress. |
| Liquidity / capacity | Addressed approximately | Original 1% trailing-ADV cap, ten-position, name, cash and sector constraints unchanged. |
| OOS | **Not available by design** | Sealed OOS was correctly not opened after validation failure. |

## 4. Robustness

### Cost stress — validation

| Cost multiple | CAGR | Sharpe | PF |
|---|---:|---:|---:|
| 1x | 0.91% | 0.320 | 1.39 |
| 2x | 0.83% | 0.292 | 1.34 |
| 5x | -0.00% | 0.016 | 1.11 |
| 10x | -0.59% | -0.177 | 0.91 |

### Parameter sensitivity — validation

| Retest window | Trades | CAGR | Sharpe | PF |
|---|---:|---:|---:|---:|
| 10 sessions | 51 | 0.92% | 0.335 | 1.42 |
| **15 frozen** | **58** | **0.91%** | **0.320** | **1.39** |
| 20 sessions | 61 | 0.83% | 0.289 | 1.32 |

The surface is smooth and positive, so the entry effect is not a cliff. It is
simply too small. Monte Carlo places observed drawdown inside its normal range.

### Outlier trim

- Validation full expectancy +1.70%, PF 1.39.
- Drop top five: expectancy **-1.96%**, PF **0.59**.
- Drop top ten: expectancy **-3.72%**, PF **0.30**.

The result depends heavily on a few winners and fails the required trim test.

## 5. Red flags

1. Net validation CAGR misses the 20% target by more than nineteen percentage points.
2. Preliminary score 41 misses the >80 gate; statistical significance is absent.
3. Bootstrap crosses zero and DSR is 1.1% after the honest trial count.
4. Top-five trim reverses expectancy despite a smooth window surface.
5. Low MDD reflects sparse exposure, not a high-return low-risk edge.

## 6. Verdict

**41/100 — Weak; Reject.** The pivot retest is a genuine, causal improvement
over MA20 pullback on recent PIT data, but it is neither statistically secure
nor remotely capable of the required 20% CAGR. Per the frozen rule the
2000-2005 untouched OOS remains sealed. Files: timestamped JSON/Markdown,
primary daily returns and trade CSVs under `backtests/pivot_retest_v2/results/`.
