# Trial 542 Standalone Relative-MA60 Verification

Verified: 2026-08-02
Verdict: **WORSENS**
Backtest Score: **20/100 — Reject**

## Result

This isolated experiment removed VCP detection, breakout confirmation, the
MA20 pullback, pattern stop and Edge Rank from entry. The only entry event was
a false-to-true transition in the strict standalone condition:

```python
stock_close > stock_ma60
and stock_ma60_slope_20d > 0
and stock_ma60_slope_20d > spy_ma60_slope_20d
```

The close-confirmed event filled at the next ticker open. To make a VCP-free
portfolio executable, the pre-return specification froze equal 10% targets,
relative-slope priority, an 8% raw-open hard stop and the existing 60-session
timeout. Capital, capacity, sector/ADV/cash constraints and two-sided costs
were retained. This is therefore a new standalone strategy, not a one-variable
comparison with the VCP baseline.

| Partition | Trades | CAGR | SPY CAGR | MDD | Sharpe | PF | Exposure-matched excess CAGR |
|---|---:|---:|---:|---:|---:|---:|---:|
| Train 2016H2–2018H1 | 108 | 21.17% | 9.70% | -10.81% | 1.643 | 2.874 | +6.71% |
| Validation 2019–2021 | 218 | 6.27% | 22.87% | -35.61% | 0.411 | 1.312 | -11.84% |
| Best-available OOS 2022–2026Q1 | 305 | 4.88% | 12.05% | -25.52% | 0.357 | 1.222 | -5.83% |
| Full diagnostic | 588 | 7.59% | 15.51% | -29.60% | 0.534 | 1.392 | -5.99% |

The 21.17% train CAGR collapsed to 6.27% in validation and 4.88% in the latest
partition. Full-period capital grew 107.34%, versus 320.65% for SPY over the
matched simulation dates. Full mean trade return was +1.77%, but median trade
return was -8.18%; mean matched-SPY excess was -0.56% and its 95% bootstrap CI
was [-1.55%, +0.47%]. In the latest partition, drop-best-five expectancy was
-0.03% and winsorized expectancy was only +0.16%.

The portfolio was not defensively underinvested: full average exposure was
93.32% and average positions were 9.86/10. Instead, capacity was saturated.
Of 18,058 emitted full-period signals, 17,461 were rejected because the name
was already held or all ten slots were occupied. This makes same-open priority
economically important and confirms that a trade-level-only view would be
misleading.

## Cost stress

The initial audit found that the shared simulator measured its 8% stop from
the cost-loaded fill, so changing cost multipliers also moved the stop. Before
finalising results, the standalone adapter was corrected to hold the stop at
8% below the raw open for every multiplier. A deterministic regression test
now covers this. Final cost results degrade monotonically:

| Partition | 1x CAGR | 2x | 5x | 10x |
|---|---:|---:|---:|---:|
| Train | 21.17% | 17.98% | 15.03% | 10.35% |
| Validation | 6.27% | 4.90% | 0.83% | -5.16% |
| Best-available OOS | 4.88% | 3.43% | -0.37% | -5.83% |
| Full | 7.59% | 6.29% | 2.64% | -2.98% |

## Bias and validity

| Check | Assessment |
|---|---|
| Lookahead/calendar | Absent in signal construction: aligned completed common dates, rising edge at close, next-ticker-session fill |
| PIT membership | Enforced on both signal and fill dates |
| SPY use | Real SPY benchmark only; never held |
| Costs/capacity | Actual portfolio simulation with fixed constraints and monotonic 1x/2x/5x/10x stress |
| Multiple testing | Present and disclosed: post-grid MA60, Trial 542, total declared units 541 |
| Survivorship | Unresolved: 91.31% price coverage and incomplete delisted coverage |
| Sector history | Current sector labels, not point-in-time; unknown historical names remain grouped as Unknown |
| OOS | Latest period is best-available only and already contaminated by wider repository research |
| Stability | Failed: strong train result collapses in validation and latest periods |

## Score

A/B/C/D = 18/10/4/14, measured 46/83 and normalized raw 55/100. The
unresolved-survivorship cap limits the final score to **20/100 — Reject**.
The result also fails the goal's 20% latest-period net CAGR requirement.

## Verification

- Nine standalone deterministic tests passed.
- Full repository suite: **583 passed in 2.12s**.
- `py_compile` and `git diff --check` passed before handoff.
- Ruff/Mypy remain uninstalled/unconfigured; no lint/static-type claim is made.

## Artifacts

- `frozen_spec.md`
- `results/ma60_only_2026-08-02_161116.json`
- `results/ma60_only_2026-08-02_161116.md`
- Four partition-specific signal, trade and equity CSV triplets.
- Exact command in the result report and research command ledger.

No frozen VCP strategy file was modified, and no 2000–2005 data was accessed.
