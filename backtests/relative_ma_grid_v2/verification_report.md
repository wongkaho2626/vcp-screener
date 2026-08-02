# Trial 522–541 Relative-MA Grid Verification

Verified: 2026-08-02
Family verdict: **NO_QUALIFYING_WINNER**
Diagnostic-leader Backtest Score: **20/100 — Reject**

## Result

The grid evaluated MA periods 10, 20, …, 200 on train only. The stock-versus-
SPY percentage-slope window remained fixed at 20 sessions. Every one of the 20
cells counted toward multiplicity; no parameter was chosen using validation or
OOS.

No cell simultaneously satisfied the frozen five-part gate. Validation and
best-available OOS therefore remained sealed.

The highest raw train result was MA60: 17 trades, 1.95% CAGR versus 1.60%
baseline, 0.873 Sharpe, PF 2.910 and +6.83 points qualifying-minus-rejected
matched excess. It was ineligible because it had fewer than 20 trades and
drop-best-five expectancy was -0.45%. This is exactly the thin-sample,
outlier-dependent pattern the gate was designed to reject.

Among cells with at least 20 executed trades, the exposure-excess diagnostic
leader was MA20: 23 trades, 1.13% CAGR, 0.593 Sharpe and PF 1.478. It failed
three gates: CAGR lift was -0.47 points, qualifying-minus-rejected matched
excess was -1.34 points, and drop-best-five expectancy was -2.12%.

The grid was not smooth. MA60 stood out between weaker adjacent MA50 and MA70
cells; most longer periods had 13–20 trades and negative outlier-trimmed
expectancy. The apparent MA60 peak is not credible evidence of a robust edge.

## Score

The MA20 diagnostic leader scored A/B/C/D 10/14/4/9, measured 37/83 and
normalized raw 45/100. Incomplete delisted coverage applies the 20-point
survivorship cap; absent OOS/WFA also applies a 55 cap. Final score is 20/100.
This score belongs to a rejected discovery diagnostic, not a selected strategy.

## Bias and validity

| Check | Assessment |
|---|---|
| Lookahead/calendar | Absent in implementation: common completed stock/SPY dates and unchanged next-open fill |
| PIT membership | Enforced at detection, signal and fill |
| Costs/capacity | Frozen model retained in every portfolio cell |
| Multiple testing | Present and disclosed: twenty cells; declared trials 520 → 540 |
| Survivorship | Unresolved: 91.31% coverage and incomplete delisted coverage |
| OOS | Not accessed because no train winner qualified |
| Parameter stability | Failed: thin MA60 peak and no all-gates plateau |

## Verification

- Seven grid-specific deterministic tests passed.
- Full repository suite: **574 passed in 1.87s**.
- `py_compile` and `git diff --check` passed before handoff.
- Ruff/Mypy remain uninstalled/unconfigured; no lint/static-type claim is made.

## Artifacts

- `frozen_spec.md`
- `results/relative_ma_grid_2026-08-02_133338.json`
- `results/relative_ma_grid_2026-08-02_133338.md`
- Baseline plus twenty grid-cell signal/trade/equity CSV triplets.
- Exact command in the report and research command ledger.

No frozen strategy or portfolio mechanic changed, and no 2000–2005 data was
accessed.
