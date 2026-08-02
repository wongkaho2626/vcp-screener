# Goal Completion Matrix — 2026-08-01

## Verdict

**NOT PROVEN — ACTIVE, NOT COMPLETE.** The repository-local 2006+ evidence
boundary and capped best-available OOS process are now defined, but no frozen
strategy has passed discovery or demonstrated >=20% OOS CAGR.

## Hard-condition audit

| # | Hard condition | Current evidence | Status |
|---|---|---|---|
| 1 | Transparent raw A/B/C/D, caps and final score; no minimum score | Every recent trial reports reduced-denominator components, raw score, both applicable caps and final score. | **PASS for attempted research; final strategy absent** |
| 2 | Net portfolio CAGR >=20% after fixed costs | Trial 575's QQQ-synchronized overlay reached 15.66% contaminated OOS CAGR and 17.33% full CAGR; neither meets 20%. | **FAIL** |
| 3 | Existing 2006+ historical S&P 500 stocks only | Membership gating is implemented; executable price inputs support 2016+ signals. | **PASS for attempted research** |
| 4 | Change buy/sell signals only | Signal research changes entry/exit behavior; the OHLC repair is outcome-free shared data integrity. | **PASS** |
| 5 | Fixed sizing, positions, capital, costs and risk; no leverage | All evaluated candidates use the unchanged portfolio engine and Config. | **PASS** |
| 6 | No other assets; SPY benchmark only | Orders contain stocks only; SPY is never a holding/fallback. | **PASS** |
| 7 | Causal next-session execution | Signal/fill separation, truncation invariance and detector/portfolio parity have regression tests. | **PASS** |
| 8 | Measure PIT/delisted/survivorship coverage using current data | Inventory records 91.31% modern coverage, 69.74% prior reconstruction evidence and 135 priced ended-membership symbols. | **PASS with disclosed limitations/cap** |
| 9 | Chronological discovery, validation and frozen best-available OOS; label contamination | Trial 569–572 selected slope10 on train, opened only its validation, and kept OOS sealed after two validation gates failed. Trials 573–576 are explicitly contaminated descriptive audits; QQQ parameters were frozen only after the historical periods. | **PASS for labelling; final untouched OOS absent** |
| 10 | Full robustness panel | Complete for the non-qualifying exploratory replay; unavailable for a final strategy because none passed gates. | **INCOMPLETE for final strategy** |
| 11 | >=30 independent OOS trades; no outlier/leverage/cost/post-hoc shortcut | Trial 575 produced 91 trades on the latest partition, but the slope and QQQ overlay combination are post-hoc and the partition is contaminated; no qualifying final OOS exists. | **FAIL** |
| 12 | Read failures; predeclare novel hypothesis, density, gates and give-up criteria | Trials through 572 were frozen before their accessed returns. Trial 573 recorded the user-directed forced exit before rerunning it, but remains explicitly post-hoc because all available partitions had already been inspected. | **PASS for documentation; evidence remains descriptive** |
| 13 | Reproducible spec, command, code/tests, JSON/CSV/report | Trial 573 preserves code, exact command, JSON, Markdown and signal/trade/equity CSVs. | **PASS for attempts; qualifying final report absent** |
| 14 | Do not pursue 2000–2005 PIT | New workflow uses only repository-local 2006+ evidence and makes no external lookup. | **PASS** |

## Completion boundary

Score caps are acceptable but do not excuse failed performance. Completion
requires one unchanged frozen candidate to pass discovery and validation, then
produce >=20% net CAGR and >=30 independent trades on the frozen
2022–2026Q1 best-available OOS, with full robustness and transparent caps.
