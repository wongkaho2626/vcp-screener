# Trial 496–504 — Strong-Stock Character-Change Exit

Best-available frozen OOS accessed: **NO**

## Backtest Score: 20/100 — Reject

Discovery-only reduced-denominator score; it cannot qualify the strategy.

| Component | Score | Available max |
|---|---:|---:|
| A. Statistical validity | 7 | 30 |
| B. Risk-adjusted performance | 7 | 25 |
| C. Robustness (bootstrap only) | 4 | 8 |
| D. Trade quality / consistency | 0 | 20 |
| **Measured total** | **18** | **83** |
| **Normalized raw score** | **22** | **100** |
| Caps applied | Unresolved survivorship → 20; no formal OOS / WFA → 55 | |
| **Final score** | **20** | **100** |

WFA efficiency (10 points) and parameter sensitivity (7 points) were unavailable because the train gate failed. Their weight was redistributed under the reduced-denominator rule rather than silently scored as zero. The lower unresolved-survivorship cap then applies to the normalized score.

Outcome-free gate: 58 custom exits / 103 signals — **PASS**.

Train trades 88; CAGR 0.50%; Sharpe 0.228; PF 0.982; MDD -3.26%; trim-five expectancy -0.87%.

Train gate: **FAIL**

- PASS — trades>=60
- FAIL — cagr>=10pct
- FAIL — sharpe>=0.75
- FAIL — pf>1.20
- PASS — mdd>-15pct
- FAIL — drop_top_5_expectancy>0

2019–2021 validation accessed: **NO**

2022–2026Q1 best-available OOS remains sealed.

This exit-only result cannot overcome the previously established ~18.72% hindsight-perfect-exit train ceiling for the unchanged entry.
