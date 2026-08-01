# Trial 303–304 — Fresh SEC Filing Window

Formal validation accessed: **NO**

Train setups 13; mean fixed-20 label 4.54%; positive 12/13.

Holdout signals 37; trades 30; CAGR 1.26%; Sharpe 0.402; PF 1.198; MDD -2.90%; trim-5 expectancy -1.91%.

Gate: **FAIL**

- FAIL — cagr>=15pct
- FAIL — sharpe>=0.75
- FAIL — pf>1.20
- PASS — mdd>-15pct
- FAIL — drop_top_5_expectancy>0
- PASS — trades>=30

Formal validation and untouched OOS remain sealed.
