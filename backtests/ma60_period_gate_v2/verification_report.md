# Trial 551–568 Verification — User-Supplied MA60 Entry Windows

## Answer

**Yes, the supplied dates change the historical path, but they do not improve
market-relative performance.** On the best-available 2022–2026Q1 partition,
the calendar gate raises raw CAGR from 6.22% to 10.08% and improves MDD from
-23.12% to -14.17%. However, exposure-matched excess CAGR worsens from -5.57%
to **-7.32%**, and matched-window mean trade excess falls from -3.16% to
**-10.13%**. The full-period CAGR is effectively unchanged at 9.76% versus
9.71%.

Final classification: **DESCRIPTIVE_ONLY / diagnostic INCONCLUSIVE**. The
precise dates' causal provenance is unknown, only seven of 18 windows are
executable, and all available periods are already research-contaminated.

## Rule tested

Only the actual fill date is gated. Finite start/end dates are inclusive and
the 2025-04-07 interval is open-ended. A signal before a window may fill inside
it. A position opened inside a window continues after the window closes and
uses the unchanged 8% hard stop, +3R completed-close arming, next-session 24%
trailing stop, and no timeout.

The MA60 false-to-true buy condition, PIT membership, next-open execution,
capital, sizing, capacity, liquidity, sector limits and costs are unchanged.

## Fair-clock correction

An initial diagnostic run exposed a portfolio-clock mismatch: filtering early
signals caused the engine to begin CAGR at the first retained fill instead of
the incumbent's first eligible trading date. That run was invalidated. The
engine now accepts an explicit simulation start and carries cash before the
first gated entry. Corrected gated and baseline results use identical dates;
SPY CAGR matches exactly within every partition.

## Portfolio comparison

| Partition | Signals retained | Trades | Gated CAGR | Baseline | Lift | Gated MDD | Baseline MDD | Gated Sharpe | Excess-CAGR change |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Train | 82.07% | 16 | 13.56% | 13.40% | +0.16 pp | -12.54% | -13.75% | 1.078 | +0.18 pp |
| Validation | 93.48% | 47 | 8.34% | 6.72% | +1.62 pp | -31.59% | -32.96% | 0.506 | +0.65 pp |
| Best-available OOS | 64.63% | 49 | 10.08% | 6.22% | +3.86 pp | -14.17% | -23.12% | 0.743 | **-1.75 pp** |
| Full | 76.30% | 111 | 9.76% | 9.71% | +0.05 pp | -27.11% | -27.11% | 0.677 | **-1.33 pp** |

The OOS gate cuts completed trades from 99 to 49 and average exposure from
97.50% to 85.21%. Average hold rises from 112 to 200 sessions because the
changed entry/capacity path selects a smaller, longer-lived cohort. Profit
factor improves from 1.605 to 2.972 and drop-best-five expectancy improves
from -1.61% to +2.22%, but these raw-trade improvements do not translate into
benchmark-relative alpha.

## Statistical evidence

OOS mean net trade return is +9.27%, but the same holding windows earn an
average +19.41% in SPY. Mean net excess is -10.13%, t = -2.36, bootstrap 95%
CI **[-18.29%, -1.64%]**, and only 20.41% of trades beat SPY. Full-period mean
excess is -7.38%, t = -2.72, CI [-12.56%, -2.06%]. This is evidence against a
stock-selection improvement, even though lower exposure and path selection
make absolute OOS drawdown and CAGR look better.

## Cost stress

| Costs | OOS CAGR | OOS MDD | OOS PF | Full CAGR |
|---:|---:|---:|---:|---:|
| 1x | 10.08% | -14.17% | 2.972 | 9.76% |
| 2x | 9.87% | -14.21% | 2.887 | 9.56% |
| 5x | 8.85% | -14.42% | 2.546 | 8.76% |
| 10x | 7.87% | -14.77% | 2.229 | 7.34% |

Costs do not erase the raw return, but robustness to costs cannot repair the
negative market-relative result or the calendar-selection bias.

## Coverage and bias assessment

- Supplied windows: 18; executable overlaps: 7; untested: 11.
- Repository-local data cannot execute the 2002–2014 windows. They are not
  counted as zero-return periods.
- Historical membership coverage is 91.31%, with incomplete former-member and
  delisted price history; survivorship remains unresolved.
- The exact date schedule may be post-hoc. Without a causal rule that would
  announce each opening and closing date in real time, the gate is not
  deployable and cannot be treated as OOS.
- The 18 windows add at least 18 multiplicity units, raising the declared total
  from 549 to 567; endpoint-level flexibility makes 18 a lower bound.

## Backtest Score

A/B/C/D = 20/10/8/18, measured 56/83 and normalized to 67/100. The unresolved
survivorship cap and absence of valid OOS/WFA evidence reduce the final score
to **20/100 — Reject**.

## Reproduction

```bash
.venv/bin/python scripts/ma60_period_gate_experiment.py \
  --price-csv SP500_PIT_2016_2026.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --membership-csv scripts/data/sp500_membership.csv \
  --sector-json scripts/data/sp500_constituents.json \
  --baseline-json backtests/ma60_3r_trailing_v2/results/ma60_3r_trailing_2026-08-02_165231.json \
  --output-dir backtests/ma60_period_gate_v2/results \
  --iterations 1000

.venv/bin/python -m pytest \
  tests/test_ma60_period_gate_experiment.py \
  tests/test_portfolio_backtest.py \
  tests/test_ma60_only_experiment.py -q
.venv/bin/python -m pytest tests/ -q
.venv/bin/python -m py_compile \
  scripts/portfolio_backtest.py \
  scripts/ma60_only_experiment.py \
  scripts/ma60_period_gate_experiment.py
git diff --check
```

Canonical corrected artifacts use timestamp `2026-08-02_172922` under
`backtests/ma60_period_gate_v2/results/`.
