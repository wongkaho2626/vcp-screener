# Trial 441–447 — Realized Semivariance Asymmetry Lifecycle

Best-available frozen OOS accessed: **NO**

## Backtest Score: 20/100 — Reject

Discovery-only reduced-denominator score; it cannot qualify the strategy.

| Component | Score | Available max |
|---|---:|---:|
| A. Statistical validity | 7 | 30 |
| B. Risk-adjusted performance | 7 | 25 |
| C. Robustness (bootstrap only) | 0 | 8 |
| D. Trade quality / consistency | 9 | 20 |
| **Measured total** | **23** | **83** |
| **Normalized raw score** | **28** | **100** |
| Caps applied | Unresolved survivorship → 20; no formal OOS / WFA → 55 | |
| **Final score** | **20** | **100** |

WFA efficiency (10 points) and parameter sensitivity (7 points) were unavailable because the train gate failed. Their weight was redistributed under the reduced-denominator rule rather than silently scored as zero. The lower unresolved-survivorship cap then applies to the normalized score.

Train states 4165; signals 104; trades 73; CAGR -0.03%; Sharpe 0.002; PF 1.120; MDD -6.04%; trim-5 expectancy -1.09%.

Train gate: **FAIL**

- PASS — trades>=60
- FAIL — cagr>=10pct
- FAIL — sharpe>=0.75
- FAIL — pf>1.20
- PASS — mdd>-15pct
- FAIL — drop_top_5_expectancy>0

2019–2021 validation accessed: **NO**

2022–2026Q1 best-available OOS remains sealed.
