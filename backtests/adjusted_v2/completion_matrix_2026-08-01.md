# Goal Completion Matrix — 2026-08-01

## Verdict

**NOT PROVEN — BLOCKED, NOT COMPLETE.** No frozen strategy has passed its
prespecified discovery gate, and the untouched 2000–2005 OOS cannot be opened
because the workspace lacks survivorship-safe prices, delisting returns and a
compatible security master for that interval. The success thresholds have not
been changed.

## Hard-condition audit

| # | Hard condition | Evidence | Status |
|---|---|---|---|
| 1 | Same frozen OOS strategy scores **>80/100** under the backtest-analyst rubric and hard caps | The existing formal baseline scores 41. Unresolved survivorship bias in the intended OOS invokes the rubric's 20/100 hard cap. No candidate has authority to enter formal validation. | **FAIL / not demonstrated** |
| 2 | Net portfolio CAGR **>=20%** after fixed realistic costs | Date-aligned Trial 288 reconstruction reached 4.82% and failed its gate. Its user-requested 2022–2026 exploratory replay produced 0.05% net CAGR on 89 trades. No untouched-OOS CAGR exists. | **FAIL / contradicted by available replay** |
| 3 | Point-in-time S&P 500 constituent stocks only | Membership-on-signal/fill checks and a stocks-only universe are implemented for evaluated data. The intended final 2000–2005 PIT execution dataset is absent. | **PARTIAL: infrastructure verified; final OOS missing** |
| 4 | Change buy/sell signals only | Research changes are confined to causal entry filters/timing and stop, profit, trailing or time-exit rules. | **PASS for attempted research** |
| 5 | Keep sizing, position cap, capital, cost model and risk limits fixed; no leverage | All evaluated candidates use the repository's frozen portfolio construction and cost/risk settings. | **PASS for attempted research** |
| 6 | No crypto, ETF, options, futures, FX or fallback; SPY benchmark only | Candidate holdings are individual PIT S&P 500 stocks. SPY is never submitted as an order. | **PASS for attempted research** |
| 7 | Fully causal; close-confirmed signals fill no earlier than next session | Signal/fill separation, next-session execution and fill-time/as-of stop checks are covered by the portfolio tests. | **PASS for evaluated rules** |
| 8 | PIT membership, delisted names where possible, and explicit survivorship coverage | Modern 2016–2026 reconstruction has 91.39% member-day coverage but was used during discovery. Legacy 2006–2015 has 69.74%. Public 2000–2005 recovery has only 58.35% and was rejected outcome-free. | **FAIL for untouched OOS** |
| 9 | Separate discovery/train, validation and untouched OOS; freeze before opening OOS | At user direction, 2022–2026 was opened only as a predeclared exploratory replay after Trial 288 had already failed. It is now explicitly contaminated and cannot be formal validation or untouched OOS. The intended 2000–2005 OOS remains unavailable. | **PARTIAL; no qualifying untouched OOS** |
| 10 | Walk-forward, cost stress, sensitivity, bootstrap/Monte Carlo, folds/regimes, outlier trim, PSR/DSR, MDD, Sharpe, Sortino, Calmar, PF and trade count | These checks are complete for the non-qualifying existing-data replay and all reject a robust edge. They still cannot be claimed for a qualifying final frozen OOS strategy because none exists. | **PASS for exploratory replay; incomplete for final strategy** |
| 11 | At least 30 independent OOS trades; no leverage, cost omission, outlier dependence or post-hoc period choice | The replay has 89 trades but is not untouched OOS; drop-top-five expectancy is -1.71% and 2x-cost CAGR is negative. No qualifying untouched-OOS trades exist. | **FAIL / wrong evidence class** |
| 12 | Read prior README/specs/reports/failures; predeclare novel, explainable hypotheses | Trials through 327 have frozen pre-outcome specifications, explicit hypotheses and recorded rejection evidence. | **PASS** |
| 13 | Preserve reproducible spec, commands, JSON/CSV and full verification report | Attempted candidates preserve frozen specs, commands, result JSON/Markdown and trade/equity CSV. A successful final verification report cannot exist until the hard conditions are met. | **PASS for attempts; final artifact missing** |

## Evidence boundary

- Full code/test validation demonstrates execution-engine integrity; it does
  **not** demonstrate a profitable strategy.
- Low drawdown, a positive profit factor, or 30+ discovery trades cannot
  substitute for the two simultaneous untouched-OOS thresholds.
- The 2016–2026 data cannot be relabelled as untouched because it informed
  discovery and internal holdout decisions.
- The rejected public archive cannot be patched with current survivors: doing
  so would leave confirmed survivorship bias and retain the 20-point hard cap.

## Exact blocker and unlock contract

Completion requires both a candidate that first passes its frozen discovery
and validation gates and a survivorship-safe untouched OOS dataset. The current
external blocker is the latter: no licensed/user-provided 2000–2005 daily data
with stable identifiers, PIT membership, corporate actions, delisting
prices/returns and at least 90% measured member-day coverage is available.

Acceptable unlock paths are working CRSP/WRDS entitlement or a repository-local
equivalent satisfying the fields and audit sequence in
`completion_blocker_audit.md`. On unlock, coverage must be audited without
opening strategy outcomes; only a specification frozen after successful
discovery and formal validation may be run once on untouched OOS.
