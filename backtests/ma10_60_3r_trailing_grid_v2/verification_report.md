# Trial 545–550 Verification — MA10–60 Buy Grid

## Verdict

**VALIDATION_FAIL.** Keeping the Trial 544 exit unchanged did not produce a
shorter-MA replacement that survived chronological selection. MA40, MA50 and
MA60 passed the six frozen train gates. MA60 retained the highest train
exposure-matched excess CAGR and was selected before validation. It then failed
validation on both market-relative performance and drawdown, so
best-available OOS remained sealed.

## Frozen strategy family

Each cell uses a standalone false-to-true entry requiring price above its SMA,
a positive 20-session SMA percentage slope, and a stock SMA slope strictly
above the aligned SPY SMA slope. The only searched input is SMA length:
10/20/30/40/50/60. Signals confirm at the close and fill no earlier than the
next eligible open with point-in-time membership required on both dates.

Every cell retains the 8% initial hard stop, +3R completed-close arming,
next-session 24% completed-close trail, and no timeout. Portfolio capacity,
sizing, costs, liquidity and sector limits are unchanged.

## Train grid

| MA | Trades | Armed | CAGR | Exposure-matched excess CAGR | Sharpe | MDD | PF | Drop-best-five | Gate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 10 | 36 | 16 | 5.19% | -5.00% | 0.437 | -16.19% | 1.833 | -2.91% | FAIL |
| 20 | 30 | 11 | 10.05% | -0.10% | 0.769 | -12.99% | 2.516 | -2.22% | FAIL |
| 30 | 31 | 11 | 5.94% | -4.82% | 0.493 | -14.89% | 2.393 | -3.23% | FAIL |
| 40 | 21 | 12 | 12.44% | +1.32% | 0.940 | -16.08% | 6.245 | +2.54% | PASS |
| 50 | 20 | 12 | 14.03% | +2.29% | 0.990 | -17.53% | 6.485 | +2.50% | PASS |
| 60 | 18 | 9 | 13.40% | +2.48% | 1.049 | -13.75% | 7.692 | +3.51% | PASS / SELECTED |

MA50 had the highest raw train CAGR, but the frozen objective was
exposure-matched excess CAGR, not raw CAGR. MA60 led that objective at +2.48%
and also had the best Sharpe, drawdown and trimmed expectancy among the three
qualified cells. Choosing MA50 after viewing raw CAGR would violate the frozen
selection rule.

## Validation failure

Selected MA60 completed 48 validation trades and returned 6.72% CAGR, but SPY
returned 22.87%. Exposure-matched excess CAGR was **-11.04%**, MDD was
**-32.96%**, and matched-window mean trade excess was -9.92% with t = -2.93
and bootstrap 95% interval [-16.62%, -3.66%]. It therefore failed:

- `exposure_matched_excess_cagr > 0`
- `MDD > -30%`

The other four validation gates passed, although drop-best-five expectancy was
only +0.004%, effectively flat. Validation performance was behind SPY in every
displayed calendar segment. The best-available 2022–2026Q1 OOS was not opened,
and no OOS cost stress or final incumbent comparison was permitted.

## Statistical score and limitations

The selected train cell scored A/B/C/D = 16/15/4/18, or 53/83 measured points,
normalized to 64/100. The unresolved survivorship/delisted-coverage cap and
absence of an opened OOS/WFA segment cap the final **Backtest Score at 20/100
(Reject)**. Six cells raise declared multiplicity from 543 to 549. Coverage is
91.31%, but historical prices remain incomplete for some former members.

Train samples are thin because removing the timeout creates very long holding
periods and capacity saturation: average train holds range from 168 to 326
sessions. Even the selected cell has only 18 completed train trades, so its
apparently high PF is unstable and independently subject to the under-30-trade
hard cap.

## Reproduction

```bash
.venv/bin/python scripts/ma10_60_3r_trailing_grid_experiment.py \
  --price-csv SP500_PIT_2016_2026.csv \
  --coverage-json backtests/pivot_retest_v2/coverage_2016_2026.json \
  --membership-csv scripts/data/sp500_membership.csv \
  --sector-json scripts/data/sp500_constituents.json \
  --incumbent-json backtests/ma60_3r_trailing_v2/results/ma60_3r_trailing_2026-08-02_165231.json \
  --output-dir backtests/ma10_60_3r_trailing_grid_v2/results \
  --iterations 1000

.venv/bin/python -m pytest \
  tests/test_ma60_only_experiment.py \
  tests/test_ma10_60_3r_trailing_grid_experiment.py \
  tests/test_portfolio_backtest.py -q
.venv/bin/python -m pytest tests/ -q
.venv/bin/python -m py_compile \
  scripts/ma60_only_experiment.py \
  scripts/ma10_60_3r_trailing_grid_experiment.py
git diff --check
```

The timestamped JSON, Markdown, six train signal/trade/equity triplets, and
selected validation triplet are stored under
`backtests/ma10_60_3r_trailing_grid_v2/results/`.
