# Trial 520 MA50-Slope Verification

Verified: 2026-08-02
Verdict: **INCONCLUSIVE — practical reject**
Backtest Score: **14/100 — Reject**

## Result

The frozen gate required the signal-date adjusted close to be strictly above
SMA50 and SMA50 to be strictly above its value 20 stock sessions earlier. It
retained 28/34 train, 94/105 validation and 149/173 best-available OOS signals.

| Fold | Baseline CAGR | Primary CAGR | Baseline / primary trades | Primary Sharpe | Primary PF | Primary drop-best-5 expectancy |
|---|---:|---:|---:|---:|---:|---:|
| Train | 1.60% | 1.36% | 32 / 26 | 0.574 | 1.498 | -1.97% |
| Validation | 1.14% | 1.14% | 86 / 78 | 0.292 | 1.313 | -0.77% |
| Best-available OOS | -3.22% | -2.81% | 131 / 111 | -0.725 | 0.621 | -3.22% |

The OOS portfolio lost 11.77% in total with -2.81% CAGR and -14.25% MDD.
Mean net trade return was -1.84%; mean matched-SPY excess was -2.60%, bootstrap
95% CI [-4.16%, -0.94%], with entry-month clustered t-stat -3.53. Although the
gate improved OOS CAGR by 0.41 percentage points and baseline pass trades beat
fail trades by 0.98 points of matched excess, it did so inside a losing
strategy. Train CAGR worsened, validation CAGR was unchanged, and every fold's
drop-best-five expectancy was negative.

At 2x/5x/10x costs, primary OOS CAGR was -3.34%/-3.84%/-4.97%. Calendar-year
results were inconsistent: the gate helped in 2023 and 2025, materially hurt
2024, and remained negative in every displayed OOS year. It therefore fails
the positive-CAGR, outlier, cost and consistency requirements.

## Bias and validity

| Check | Assessment |
|---|---|
| Lookahead | Absent in implementation: completed signal close only; existing next-open fill |
| Calendar alignment | Stock's actual valid sessions; weekend resolves backward; no future backfill |
| PIT membership | Enforced on detection, signal and fill dates |
| Survivorship | Unresolved: 91.31% member-day coverage and incomplete delisted coverage |
| Costs/liquidity | Existing two-sided costs, ADV/cash/sector/capacity limits; 2x/5x/10x stress |
| Overfitting | One frozen 50/20 definition; no parameter search, but substantial prior-research contamination |
| OOS | Best-available 2022–2026Q1 only; not genuinely untouched |

## Verification

- Focused deterministic suite: 11 passed.
- Full repository suite: 552 passed in 1.91s.
- `py_compile`: passed.
- `git diff --check`: passed before final handoff.
- Ruff and Mypy are not installed/configured; no lint or static-type claim is made.

## Artifacts

- `frozen_spec.md`
- `results/ma50_slope_2026-08-02_125453.json`
- `results/ma50_slope_2026-08-02_125453.md`
- Twenty-seven signal/trade/equity CSVs covering three variants across three folds.
- Exact command in the Markdown report and `backtests/v2_research_commands.md`.

The experiment did not modify VCP detection, the frozen pullback entry,
portfolio sizing/ranking/capacity, stops, exits, costs or risk limits. No
2000–2005 data was accessed.
