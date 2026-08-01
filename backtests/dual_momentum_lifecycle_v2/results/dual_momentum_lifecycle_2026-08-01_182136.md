# Trial 320–323 — Dual-Momentum VCP Lifecycle

Formal validation accessed: **NO**

Train signals 198; trades 158; CAGR -1.35%; Sharpe -0.661; PF 0.615; MDD -4.40%; trim-5 expectancy -0.96%.

Train gate: **FAIL**

- PASS — trades>=60
- FAIL — cagr>=10pct
- FAIL — sharpe>=0.75
- FAIL — pf>1.20
- PASS — mdd>-15pct
- FAIL — drop_top_5_expectancy>0

Internal holdout accessed: **NO**

Formal validation and untouched OOS remain sealed.
