# Trial 340–344 — Relative-Strength-Line Leadership Lifecycle

Formal validation accessed: **NO**

## Backtest Score: 20/100 — Reject

Discovery-only reduced-denominator score; it cannot qualify the strategy.

| Component | Score | Available max |
|---|---:|---:|
| A. Statistical validity | 7 | 30 |
| B. Risk-adjusted performance | 7 | 25 |
| C. Robustness (bootstrap only) | 4 | 8 |
| D. Trade quality / consistency | 9 | 20 |
| **Measured total** | **27** | **83** |
| **Normalized raw score** | **33** | **100** |
| Caps applied | Unresolved survivorship → 20; no formal OOS / WFA → 55 | |
| **Final score** | **20** | **100** |

WFA efficiency (10 points) and parameter sensitivity (7 points) were unavailable because the train gate failed. Their weight was redistributed under the reduced-denominator rule rather than silently scored as zero. The lower unresolved-survivorship cap then reduces the normalized raw score from 33 to 20.

Train states 4165; signals 80; trades 65; CAGR 0.44%; Sharpe 0.213; PF 1.208; MDD -3.24%; trim-5 expectancy -0.82%.

Train gate: **FAIL**

- PASS — trades>=60
- FAIL — cagr>=10pct
- FAIL — sharpe>=0.75
- PASS — pf>1.20
- PASS — mdd>-15pct
- FAIL — drop_top_5_expectancy>0

Internal holdout accessed: **NO**

Formal validation and untouched OOS remain sealed.
