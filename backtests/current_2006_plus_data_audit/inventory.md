# Existing 2006+ Data Inventory and Evidence Boundary

This audit uses repository-local files only. It performs no external
lookup and does not inspect or request 2000–2005 data.

## Executable price inputs

| Input | Rows | Stocks | Dates | SPY | Adjusted OHLC flaws |
|---|---:|---:|---|---|---:|
| `SP500_PIT_2016_2026.csv` | 1,512,174 | 599 | 2014-01-02..2026-07-01 | yes | 33 |
| `backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv` | 934,273 | 557 | 2014-01-02..2021-12-31 | yes | 33 |

## Membership and survivorship

- Historical membership: 1202 symbols / 1255 intervals.
- Priced symbols with at least one ended membership interval: 135.
- 2006–2015 raw prices are absent; its prior 69.74% reconstruction exists only as coverage/report evidence and cannot run a new rule.
- 2016–2026 coverage is 91.31% in the current execution file; 2016–2018 yearly coverage remains below 90%, so unresolved survivorship must be disclosed and conservatively capped.

## Source-bar integrity

The source CSV contains 33 impossible OHLC envelopes: 30 HAR 2014
lookback bars plus one each for EVHC (2015), ANDV (2018 embargo)
and UA (2021 validation). The shared detector/portfolio loader
repairs these outcome-free after adjustment by expanding high/low
to contain open, close and the original range. No symbol is selected
or removed based on a strategy outcome.

## Contamination registry

- 2006-01-01..2015-12-31: **closed prior OOS; raw price CSV absent from current repository** (`backtests/pullback_oos/verification_report.md`).
- 2016-07-01..2018-06-30: **heavily reused discovery/train** (`backtests/adjusted_v2/research_status_2026-08-01.md`).
- 2019-01-01..2021-12-31: **reused validation/internal holdout** (`backtests/adjusted_v2/research_status_2026-08-01.md`).
- 2022-01-01..2026-03-31: **opened exploratory replay; not untouched** (`backtests/exploratory_existing_data_replay/results/verification_report.md`).

## Frozen best-available chronology

- discovery_train: 2016-07-01 through 2018-06-30
- embargo: 2018-07-01 through 2018-12-31
- validation: 2019-01-01 through 2021-12-31
- best_available_frozen_oos: 2022-01-01 through 2026-03-31

No period is genuinely untouched. The 2022–2026Q1 segment may be
used only as a pre-frozen best-available OOS for a genuinely new rule;
it must carry the no-genuine-OOS/contamination limitation and must not
be used to tune that rule.

## Decision

The executable research universe begins with 2014 lookback bars and
supports signals from 2016 onward. Missing 2000–2005 data is out of
scope and is not a blocker. Completion still requires >=20% net OOS
CAGR, >=30 independent OOS trades, fixed portfolio controls, causal
next-session execution, and transparent raw/final scoring.
