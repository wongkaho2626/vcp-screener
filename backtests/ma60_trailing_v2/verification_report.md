# Trial 543 MA60 8% Trailing-Stop Verification

Verified: 2026-08-02
Verdict: **WORSENS**
Backtest Score: **19/100 — Reject**

## Result

Trial 543 kept every Trial 542 standalone relative-MA60 entry and portfolio
constraint, removed the 60-session timeout, and used an 8% trailing stop below
the greatest completed close. The ratchet becomes active only on the following
session, eliminating same-bar high/low ordering assumptions. The initial stop
is fixed 8% below the raw entry open for every cost multiplier.

| Partition | Trail CAGR | Timeout CAGR | Lift | Trail MDD | MDD change | Trail Sharpe | Excess-CAGR lift |
|---|---:|---:|---:|---:|---:|---:|---:|
| Train | 8.66% | 21.17% | -12.51 pp | -19.45% | -8.64 pp | 0.775 | -10.88 pp |
| Validation | 7.38% | 6.27% | +1.11 pp | -27.03% | +8.58 pp | 0.502 | +1.17 pp |
| Best-available OOS | -6.37% | 4.88% | -11.25 pp | -35.39% | -9.87 pp | -0.333 | -10.03 pp |
| Full | -0.66% | 7.59% | -8.25 pp | -37.76% | -8.16 pp | 0.037 | -6.79 pp |

The trailing stop reduced latest average loss from -7.99% to -5.56%, but it
also cut average winners from +16.12% to +9.80% and reduced win rate from
37.7% to 31.1%. Average hold fell from 35.88 to 26.47 sessions despite removing
the timeout. Faster exits opened capacity for 411 latest trades instead of
305, increasing whipsaw and turnover. Latest PF fell from 1.222 to 0.797;
mean net trade was -0.78%, mean matched-SPY excess -2.06%, and the excess
bootstrap 95% CI was [-2.95%, -1.01%].

Only validation improved. Train, latest and full results all worsened, so the
isolated validation lift is not stable evidence. Latest 2022/2023/2025/2026
returns were negative; the exit retained only a positive 2024 result.

## Frozen decision checks

- FAIL — latest CAGR improves
- FAIL — latest exposure-matched excess CAGR improves
- PASS — at least 30 latest trades
- FAIL — latest drop-best-five expectancy > 0 (-1.55%)
- FAIL — latest 5x CAGR > 0 (-12.26%)
- FAIL — latest MDD no worse by more than two points (-9.87-point change)

## Cost stress

| Partition | 1x CAGR | 2x | 5x | 10x |
|---|---:|---:|---:|---:|
| Train | 8.66% | 7.78% | 5.22% | 2.01% |
| Validation | 7.38% | 5.93% | 1.71% | -4.81% |
| Best-available OOS | -6.37% | -8.04% | -12.26% | -19.33% |
| Full | -0.66% | -2.24% | -6.36% | -12.19% |

Costs degrade monotonically. The strategy is already negative at standard
costs in the latest and full periods.

## Bias and validity

| Check | Assessment |
|---|---|
| Lookahead | Absent in implementation: completed-close watermark ratchets only after current stop evaluation |
| Same-bar ordering | Avoided: today's close-derived stop is active from the next session |
| Timeout removal | Verified: no timeout exits; 777/778 full exits were trailing stops and one was end-data liquidation |
| PIT/benchmark | Signal and fill membership enforced; real SPY benchmark only |
| Costs/capacity | Actual path-dependent portfolio rerun at 1x/2x/5x/10x costs |
| Multiple testing | Present and disclosed: Trial 543, 542 total declared units |
| Survivorship | Unresolved: 91.31% coverage and incomplete delisted coverage |
| OOS | Best-available only and contaminated by prior research |
| Right censoring | One latest/full position liquidated at the final price boundary |

## Score

A/B/C/D = 7/0/0/9, measured 16/83 and normalized raw **19/100**. The raw score
is already below the 20-point unresolved-survivorship cap, so final score is
**19/100 — Reject**.

## Verification

- Six new deterministic tests cover trailing causality, timeout removal,
  parameter validation and frozen verdict logic.
- Full repository suite: **589 passed in 2.40s**.
- `py_compile` and `git diff --check` passed before handoff.
- Ruff/Mypy remain uninstalled/unconfigured; no lint/static-type claim is made.

## Artifacts

- `frozen_spec.md`
- `results/ma60_trailing_2026-08-02_163423.json`
- `results/ma60_trailing_2026-08-02_163423.md`
- Four partition-specific signal, trade and equity CSV triplets.
- Exact command in the report and research command ledger.

No 2000–2005 data was accessed.
