# Trial 521 Relative-MA50-Slope Verification

Verified: 2026-08-02
Verdict: **INCONCLUSIVE — practical reject**
Backtest Score: **14/100 — Reject**

## Result

This is the requested stock-versus-SPY slope strategy. Stock and SPY SMA50s
use identical actual common dates. Their normalized 20-session percentage
changes are compared; stock slope must be strictly positive and strictly above
SPY slope, while stock close must be strictly above stock SMA50.

| Fold | Baseline CAGR | Primary CAGR | Primary trades | Primary Sharpe | Primary PF | Primary drop-best-5 |
|---|---:|---:|---:|---:|---:|---:|
| Train | 1.60% | 0.84% | 20 | 0.383 | 1.368 | -2.95% |
| Validation | 1.14% | 1.28% | 60 | 0.363 | 1.526 | -0.50% |
| Best-available OOS | -3.22% | -2.89% | 94 | -0.787 | 0.541 | -3.92% |

The gate retained 71.1% of OOS signals and reduced portfolio loss by 0.33 CAGR
points, primarily through lower exposure. It did not improve stock selection:
within the unchanged baseline trade set, qualifying OOS trades underperformed
rejected trades by 1.24 percentage points of matched-SPY excess. The primary's
mean OOS matched excess was -3.44%, bootstrap 95% CI [-4.99%, -1.78%], with
entry-month clustered t-stat -4.55.

The OOS portfolio lost 12.05% in total, CAGR -2.89%, Sharpe -0.787, Sortino
-0.991, PF 0.541 and MDD -14.46%. Primary CAGR at 2x/5x/10x costs was
-3.38%/-4.01%/-4.86%. It was negative in every displayed OOS calendar year,
worsened 2022, 2024 and 2026, and failed the train, positive-CAGR, cost and
outlier requirements. Validation improvement alone is insufficient.

## Bias and validity

| Check | Assessment |
|---|---|
| Lookahead | Absent in implementation: signal-close data only; unchanged next-open fill |
| Calendar alignment | Stock and SPY intersected on actual common dates; no independent index subtraction |
| Price convention | Adjusted close for both legs through the repository CSV convention |
| PIT membership | Enforced at detection, signal and fill |
| SPY use | Benchmark/signal comparator only; never a position or fallback |
| Survivorship | Unresolved: 91.31% member-day coverage and incomplete delisted coverage |
| Overfitting | One frozen 50/20/zero definition; no parameter search, but prior research contamination remains |
| OOS | 2022–2026Q1 is best-available, not genuinely untouched |

## Verification

- Focused deterministic tests: 15 passed.
- Full repository suite: 567 passed in 1.84s.
- `py_compile`: passed.
- `git diff --check`: passed before handoff.
- Ruff/Mypy are not installed or configured; no lint/static-type claim is made.

## Artifacts

- `frozen_spec.md`
- `results/relative_ma50_slope_2026-08-02_132450.json`
- `results/relative_ma50_slope_2026-08-02_132450.md`
- Twenty-seven signal/trade/equity CSVs for three variants across three folds.
- Exact command in the Markdown report and research command ledger.

No frozen detection, entry timing, exit, stop, portfolio sizing/ranking,
capacity, costs or risk constraint changed. No 2000–2005 data was accessed.
