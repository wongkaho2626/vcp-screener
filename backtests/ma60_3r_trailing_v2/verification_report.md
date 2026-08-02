# Trial 544 Verification — 8% Hard Stop, 3R-Armed 24% Trail

## Verdict

**INCONCLUSIVE.** The requested exit improved the standalone MA60 strategy's
best-available OOS CAGR from 4.88% to 6.22%, improved maximum drawdown from
-25.52% to -23.12%, and remained profitable at 5x costs. It did not pass the
prespecified outlier-robustness gate: removing the five best OOS trades changed
mean net expectancy from +3.62% to **-1.61%**.

This is exploratory best-available OOS, not untouched OOS. The strategy still
falls well short of the 20% net-CAGR goal and materially trails SPY.

## Frozen rule and causal execution

- Entry is unchanged from Trial 542: the standalone relative-MA60 condition
  changes from false to true; there is no VCP, MA20 pullback, or Edge Rank.
- A close-confirmed signal fills no earlier than the next eligible open.
- Initial stop is 8% below the raw entry open. One R is the cost-loaded fill
  price minus that fixed initial stop.
- The initial stop remains active until a completed close reaches entry + 3R.
- After the daily stop check, that close arms the rule and sets the next
  session's stop to the greater of the old stop and 76% of the highest
  completed close. The stop can only ratchet upward.
- No timeout is used. Positions open at a partition boundary are liquidated at
  the last close for accounting and marked `end_of_data`.

The frozen specification is in `backtests/ma60_3r_trailing_v2/frozen_spec.md`.

## Portfolio comparison

| Partition | Trades | Armed | New CAGR | Timeout CAGR | Immediate 8% trail | MDD | Sharpe | PF | Average hold |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Train | 18 | 9 | 13.40% | 21.17% | 8.66% | -13.75% | 1.049 | 7.692 | 325.56 |
| Validation | 48 | 23 | 6.72% | 6.27% | 7.38% | -32.96% | 0.437 | 2.271 | 163.33 |
| Best-available OOS | 99 | 31 | 6.22% | 4.88% | -6.37% | -23.12% | 0.442 | 1.605 | 112.25 |
| Full | 135 | 45 | 9.71% | 7.59% | -0.66% | -27.11% | 0.679 | 2.682 | 169.93 |

Against Trial 542, the OOS result gained 1.34 percentage points of CAGR,
7.21 points of total return, 0.085 Sharpe, and 2.40 points of drawdown. The
exposure-matched excess-CAGR improvement was only 0.263 points and its level
remained negative at -5.57% (portfolio 6.22% versus SPY 12.05%). Full-period
CAGR was 9.71% versus SPY 15.51%.

## Trade and exit audit

The OOS cohort had 99 trades: 31 armed and 68 never armed. Exit reasons were
27 armed trailing stops, 66 initial stops, and six end-of-data liquidations.
Mean net return was +3.62%, but median net return was -8.18% and win rate was
31.31%. Matched-window mean excess return was -3.16%, t = -1.23, with a
bootstrap 95% interval of [-8.09%, +1.76%]. Removing the five best trades
produced -1.61% expectancy; winsorized expectancy was only +0.47%.

The no-timeout rule lengthened OOS holding time from 35.88 to 112.25 sessions
and reduced completed trades from 305 to 99. Of 8,152 OOS signals, 8,053 were
rejected as duplicates or because the ten-position portfolio was full. This
makes results more path-dependent and capital-capacity-sensitive. The six
end-data exits are right-censored, not proof of a completed exit outcome.

## Cost stress and frozen decision checks

| Cost multiplier | OOS CAGR | OOS MDD | OOS PF |
|---:|---:|---:|---:|
| 1x | 6.22% | -23.12% | 1.605 |
| 2x | 5.57% | -23.65% | 1.558 |
| 5x | 3.63% | -26.00% | 1.393 |
| 10x | 1.92% | -27.70% | 1.217 |

Five of six frozen checks passed: OOS CAGR improved, exposure-matched excess
CAGR improved, trade count exceeded 30, 5x-cost CAGR stayed positive, and MDD
did not worsen by more than two points. The positive drop-best-five expectancy
check failed, forcing `INCONCLUSIVE`.

## Backtest Score and limitations

The computable A/B/C/D score was 56/83, normalized to 67/100. The unresolved
survivorship/delisted-coverage cap reduced the final score to **20/100
(Reject)**. Coverage is 91.31%; 599 of 720 universe symbols were usable and
several former members have missing or insufficient price history. All periods
have been exposed to extensive prior research, so no partition is untouched.

## Reproduction and verification

```bash
.venv/bin/python scripts/ma60_3r_trailing_experiment.py \
  --price-csv SP500_PIT_2016_2026.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --membership-csv scripts/data/sp500_membership.csv \
  --sector-json scripts/data/sp500_constituents.json \
  --timeout-json backtests/ma60_only_v2/results/ma60_only_2026-08-02_161116.json \
  --immediate-trail-json backtests/ma60_trailing_v2/results/ma60_trailing_2026-08-02_163423.json \
  --output-dir backtests/ma60_3r_trailing_v2/results \
  --iterations 1000

.venv/bin/python -m pytest \
  tests/test_portfolio_backtest.py \
  tests/test_ma60_3r_trailing_experiment.py -q
.venv/bin/python -m pytest tests/ -q
.venv/bin/python -m py_compile \
  scripts/portfolio_backtest.py \
  scripts/ma60_3r_trailing_experiment.py
git diff --check
```

The timestamped JSON, Markdown, signal CSV, trade CSV, and daily equity CSV
artifacts are under `backtests/ma60_3r_trailing_v2/results/`. Final full-suite
test counts are recorded after verification in the repository status files.
