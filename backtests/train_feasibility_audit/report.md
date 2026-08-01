# Train-Only Signal-Density and Oracle Feasibility Audit

Generated 2026-08-01 from 2016-07-01 through 2021-12-31 only. Validation and
untouched OOS were not accessed. PIT member-day coverage was 91.31%; 42
out-of-membership detections were removed and SPY remained benchmark-only.

## Result

| Cell | Signals | Trades | Net CAGR | Avg exposure | Avg positions | Avg holding sessions | Invested sessions |
|---|---:|---:|---:|---:|---:|---:|---:|
| Immediate detection | 389 | 347 | 0.25% | 10.97% | 1.95 | 7.75 | 71.2% |
| Pivot retest | 36 | 34 | 1.77% | 6.15% | 0.97 | 38.91 | 45.8% |
| Down-close pivot hold | 61 | 55 | 2.39% | 9.87% | 1.88 | 44.09 | 69.2% |
| Future-winner oracle | 152 | 140 | 6.38% | 8.59% | 1.42 | 13.68 | 58.7% |

The densest causal entry uses only 10.97% average capital. As a scale
diagnostic, a 20% portfolio return at that exposure would require roughly 182%
annual return on exposed capital under a linear approximation.

## Explicit lookahead oracle

The oracle inspects each of the 389 immediate-detection signals' future
baseline stop/60-bar outcome and retains only the 152 positive ones. It then
runs those signals through the unchanged portfolio engine, including costs,
Edge sizing, ten-position/name/sector/cash/ADV constraints and rejection rules.
All 140 trades actually admitted by the portfolio win, yet CAGR is only 6.38%.

This oracle is **non-causal, non-deployable and never scoreable**. It is not a
formal upper bound over different exit rules or re-entry mechanisms, and a
perfect optimizer could choose among conflicting positive signals more
efficiently. It does show that entry filtering alone cannot plausibly bridge
the gap while the baseline stop and 60-bar exit remain unchanged. Further
research should change sell/re-entry mechanics rather than add another
minor entry-quality filter.

Machine-readable result:
`train_feasibility_2026-08-01_125202.json`.
