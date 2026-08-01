# Trial 334–339 — Signed Path-Efficiency VCP Lifecycle

Formal validation accessed: **NO**

## Backtest Score: 17/100 — Reject

Discovery-only reduced-denominator score; it cannot qualify the strategy.

| Component | Score | Available max |
|---|---:|---:|
| A. Statistical validity | 7 | 30 |
| B. Risk-adjusted performance | 7 | 25 |
| C. Robustness (bootstrap only) | 0 | 8 |
| D. Trade quality / consistency | 0 | 20 |
| **Measured total** | **14** | **83** |
| **Normalized raw score** | **17** | **100** |
| Caps applied | Unresolved survivorship → 20; no formal OOS / WFA → 55 | |
| **Final score** | **17** | **100** |

WFA efficiency (10 points) and parameter sensitivity (7 points) were unavailable because the train gate failed. Their weight was redistributed under the reduced-denominator rule rather than silently scored as zero. The lower unresolved-survivorship cap is then applied; the normalized raw score of 17 is already below it.

Train states 4165; signals 134; trades 109; CAGR -0.74%; Sharpe -0.353; PF 0.895; MDD -3.67%; trim-5 expectancy -0.93%.

Train gate: **FAIL**

- PASS — trades>=60
- FAIL — cagr>=10pct
- FAIL — sharpe>=0.75
- FAIL — pf>1.20
- PASS — mdd>-15pct
- FAIL — drop_top_5_expectancy>0

Internal holdout accessed: **NO**

Formal validation and untouched OOS remain sealed.
