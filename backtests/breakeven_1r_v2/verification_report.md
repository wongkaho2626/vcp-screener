# Backtest Verification Report — pivot-retest plus 1R break-even stop

Evaluated 2026-08-01 under the pre-result frozen spec. Untouched OOS remained sealed.

## Backtest Score: 25 / 100 — Weak (validation-only preliminary score)

| Component | Score | Max |
|---|---:|---:|
| A. Statistical Validity & Significance | 7 | 30 |
| B. Risk-Adjusted Performance | 7 | 25 |
| C. Robustness & Validation | 11 | 25 |
| D. Trade Quality & Consistency | 0 | 20 |
| **Raw / final** | **25 / 25** | **100** |

## Executive summary

The 1R break-even ratchet harms the otherwise weakly positive pivot-retest
entry. Validation CAGR falls from **+0.91% to approximately 0.00%**, Sharpe
from 0.320 to **0.015**, and PF from 1.39 to **0.88**. Expectancy becomes
-0.52% per trade. The rule cuts normal winner volatility as well as losses;
neighbouring 0.75R/1.25R triggers do not rescue it. Reject and close.

## Metrics

| Metric | Train | Validation | Pivot-retest baseline validation |
|---|---:|---:|---:|
| Trades | 35 | 58 | 58 |
| Net CAGR | 1.24% | **-0.00%** | +0.91% |
| Sharpe | 0.457 | **0.015** | 0.320 |
| Sortino / Calmar | 0.808 / 0.355 | 0.021 / 0.000 | 0.484 / 0.219 |
| MDD | -3.49% | -5.24% | -4.17% |
| PF / expectancy | 1.66 / +2.18% | **0.88 / -0.52%** | 1.39 / +1.70% |
| t / PSR / DSR | 1.07 / 87.8% / 2.7% | **0.03 / 51.2% / 0.18%** | 0.67 / 74.9% / 1.1% |

Validation bootstrap CAGR 90% interval is **-2.25% to +2.41%**. Drop-top-5
expectancy is -3.14% (PF 0.32); drop-top-10 is -4.64% (PF 0.09).

## Cost and parameter robustness

| Validation cell | CAGR | Sharpe | PF |
|---|---:|---:|---:|
| Frozen 1R, 1x cost | -0.00% | 0.015 | 0.88 |
| 2x cost | -0.15% | -0.039 | 0.83 |
| 5x cost | -0.95% | -0.334 | 0.66 |
| 10x cost | -1.56% | -0.537 | 0.53 |
| 0.75R diagnostic | +0.10% | 0.050 | 0.82 |
| 1.25R diagnostic | +0.06% | 0.035 | 0.91 |

The neighbouring cells are smooth but all economically null with PF below one.

## Bias assessment

Lookahead is absent: the +1R ratchet activates only after a confirming close
and is applied from the following session; a test ensures the activation bar's
low cannot trigger it retroactively. PIT coverage is 91.31% with membership
gating. Costs, liquidity, sizing and portfolio caps are unchanged. DSR uses
197 trials. The OOS lock was respected.

## Verdict

**25/100 — Weak; Reject.** A single break-even ratchet is not a free reduction
in risk; it removes the path flexibility needed by the strategy's few winners.
No further R-threshold search is justified, and untouched OOS remains sealed.
