# VCP Screener & 10-Year Backtest

Screen S&P 500 / Russell 2000 stocks for **Mark Minervini's Volatility
Contraction Pattern (VCP)** and backtest the pattern over the last 10 years.

Identifies Stage 2 uptrend stocks forming tight bases with contracting
volatility near breakout pivot points, and lets you study how those setups
resolved historically (breakout / stop-hit / timeout) across a whole universe.

Data source: Yahoo Finance via `yfinance` — **no API key required** — or a
local OHLCV CSV for fully offline runs (see [Offline mode](#offline-mode)).

## Research findings (read this first)

### Current v2 verification status (2026-08-02)

**No strategy in this repository currently meets the deployment goal.** The
latest frozen, stocks-only Trial 288 replay used the existing point-in-time
S&P 500 reconstruction for 2022-01-01 through 2026-03-31, preserved the
portfolio sizing, holding limits, capital, risk constraints and two-sided
cost model, and allowed SPY only as a benchmark. It produced **89 trades,
0.05% net CAGR, 0.031 Sharpe, 1.059 profit factor and -6.81% MDD**. Its
Backtest Score is **25/100 raw and 20/100 after the unresolved-survivorship
hard cap**. The current goal accepts a capped score at or below 80 provided
the raw A/B/C/D score, final capped score, triggered cap and reason are all
reported honestly; this replay still fails the required net CAGR of at least
20%.

The latest prespecified discovery family, Trial 352–357, tested a causal
typical-price/volume VWAP anchored to each VCP detection date. Its fresh
below-to-above reclaim plus frozen-pivot entry and two-close AVWAP exit
produced 85 train trades, 1.62% net CAGR, 0.566 Sharpe, 1.386 profit factor and
-5.21% MDD. Removing the five largest winners changed expectancy to -0.53%,
so the train gate failed and the internal holdout/OOS stayed sealed. Its
reduced-denominator score is 51/100 raw and 20/100 after the disclosed
survivorship cap; the acceptable cap does not compensate for the failed CAGR.

Trial 358–362 then tested a distinct 20-session Chaikin Money Flow zero cross
above the frozen pivot, with a two-negative-close exit. It produced 74 train
trades, -0.23% CAGR, -0.091 Sharpe, 0.975 PF and -1.40% expectancy after
removing the five largest trades. Its score was 17/100 raw and final. The gate
failed and no later evidence partition was accessed.

Trial 363–367 tested a causal Wilder DMI(14) positive-direction crossover
above the frozen pivot. It produced 80 train trades, -0.80% CAGR, -0.350
Sharpe, 0.921 PF and -1.37% trim-5 expectancy. Its raw/final score was 17/100;
the train gate failed, so 2019–2021 validation and 2022–2026Q1 best-available
OOS stayed sealed.

Trial 368–373 tested a standard causal Parabolic SAR(0.02, 0.20) bullish flip
above the frozen pivot, with a two-close bearish-flip exit. It produced 98
train trades, -0.86% CAGR, -0.331 Sharpe, 0.699 PF and -1.66% trim-5
expectancy. Its raw/final score was 17/100; the train gate failed and every
later evidence partition stayed sealed.

Trial 374–380 prespecified a standard MACD(12,26,9) signal-line crossover
lifecycle. Its outcome-free discovery density was 79 signals, one below the
frozen minimum of 80, so the family was rejected without evaluating returns or
opening validation/OOS. The density threshold was not relaxed post hoc.

Trial 381–386 applied a canonical Donchian 55-session closing-high entry and
20-session closing-low exit. Its outcome-free density was also 79 signals, so
it was rejected without return evaluation under the same unchanged 80-signal
minimum.

Trial 387–393 tested a causal 1.5x prior-ATR bullish range-expansion ignition
with an EMA10 lifecycle exit. It produced 72 train trades, -0.63% CAGR, -0.346
Sharpe, 0.817 PF and -1.32% trim-5 expectancy. Its raw/final score was 17/100;
the train gate failed and validation/OOS remained sealed.

Trial 394–399 tested three consecutive rising closes and lows above the pivot,
with a two-prior-low failure exit. It produced 144 train trades, -1.14% CAGR,
-0.553 Sharpe, 0.700 PF and -1.01% trim-5 expectancy. Trial 400–405 then
recycled the previously validated MA20 touch-and-hold execution effect after a
pivot breakout; 85 train trades produced -1.82% CAGR, -1.056 Sharpe, 0.572 PF
and -1.84% trim-5 expectancy. Both scored 17/100 and failed before validation.

Trial 406–411 tested cumulative signed-volume participation through a fresh
20-session OBV high above the pivot and an OBV-EMA10 exit. It produced 90
train trades, -0.63% CAGR, -0.267 Sharpe, 0.704 PF and -1.62% trim-5
expectancy. Its raw/final score was 17/100; cumulative OBV did not rescue the
previously failed volume family, and later partitions remained sealed.

Trial 412–417 applied canonical 12–1 momentum as a top-quintile rank within
the contemporaneous active-VCP cohort. Its outcome-free train density was only
41 signals versus the frozen minimum of 80. The family was rejected without
evaluating returns or relaxing the threshold; validation/OOS stayed sealed.

Trial 418–424 tested a distinct 20-session natural-log-price OLS trend-quality
lifecycle: positive slope plus R-squared of at least 0.50 above the frozen
pivot, followed by a two-close trend-quality failure exit. It passed the
outcome-free density audit with 106 signals and produced 79 train trades, but
only 0.30% net CAGR, 0.138 Sharpe, 1.008 PF and -5.57% MDD. Removing the five
largest winners reduced expectancy to -1.06%. Its reduced-denominator raw
score is 29/100 and its final survivorship-capped score is 20/100 (Reject).
The train gate failed, so validation and best-available OOS stayed sealed.

Trial 425–431 then tested a 25-session Aroon extreme-recency lifecycle, which
uses the age of the most recent high versus low rather than move magnitude.
It passed density with 101 signals and produced 75 train trades, but only
0.08% net CAGR, 0.040 Sharpe, 1.022 PF and -5.83% MDD. Drop-top-five
expectancy was -1.10%. Its reduced-denominator raw score is 24/100 and final
survivorship-capped score is 20/100 (Reject). The train gate failed and later
partitions stayed sealed.

Trial 432–440 tested a causal, zero-displacement Ichimoku 9/26/52
range-midpoint equilibrium lifecycle. It passed density with 115 signals but
produced 81 train trades, -0.95% net CAGR, -0.305 Sharpe, 0.868 PF and -7.01%
MDD. Removing the five largest winners reduced expectancy to -1.65%. Its
reduced-denominator raw and final score is 17/100 (Reject). The train gate
failed, validation/OOS stayed sealed, and the frozen give-up rule closes this
range-midpoint family without changing canonical windows or thresholds.

Trial 441–447 tested a 20-session realized upside/downside semivariance-ratio
lifecycle with frozen 1.50/0.75 hysteresis. It produced 104 signals and 73
train trades, but -0.03% net CAGR, 0.002 Sharpe, 1.120 PF and -6.04% MDD.
Although untrimmed trade expectancy was +0.41%, removing the five largest
winners reduced it to -1.09%. Its normalized raw score is 28/100 and final
survivorship-capped score is 20/100 (Reject). The train gate failed and later
partitions stayed sealed.

Trial 448–454 tested a gap-adjusted 10-session regular-session versus overnight
log-return lifecycle. It passed density with 164 signals and produced 125
train trades, but only 0.33% net CAGR, 0.153 Sharpe, 1.050 PF and -4.85% MDD.
Removing the five largest winners reduced expectancy to -0.57%. Its normalized
raw score is 29/100 and final survivorship-capped score is 20/100 (Reject).
The train gate failed and later partitions stayed sealed; decomposing where
daily returns accrue does not recover the missing continuation edge.

A subsequent explicitly lookahead, train-only oracle-exit residual audit did
not score or open validation/OOS. Across 90 future-profitable perfectly timed
paths, the close before the best feasible next-open exit was a fresh five-day
closing high 84.4% of the time, stable in both train halves and after dropping
the five largest oracle returns. Down-close, SMA10-break and 5% giveback states
covered only 11.1%, 5.6% and 1.1%. This is hypothesis-generating evidence for
one prespecified sell-into-strength exit, not evidence that such an exit works.

Trial 455–466 performed that one frozen translation: the prior AVWAP reclaim
entry, held at least 10 sessions, exited next open after the first strict fresh
five-day closing high. It produced 103 signals and 83 train trades, but only
0.17% CAGR, 0.085 Sharpe, 1.009 PF and -4.91% MDD; drop-top-five expectancy was
-0.90%. Its normalized raw score is 35/100 and final survivorship-capped score
20/100 (Reject). Validation/OOS stayed sealed. Frequent coincidence at a
perfect-foresight best exit does not make the first causal occurrence useful.

Trial 467–470 next audited whether VCP entries early in a current PIT S&P 500
membership spell were dense enough to test. Fixed 90/180/365/730 calendar-day
caps emitted only 0/0/4/11 train candidates versus the frozen minimum 80. The
membership end date was never a feature; returns and all later partitions
stayed sealed.

Trial 471–477 tested a distinct supply-absorption timing mechanism: after a
>=1% gap-up closed below its open, require a close above that rejection bar's
frozen high and the VCP pivot within five sessions. The outcome-free audit
found only 27 signals across 21 symbols from 4,165 active setup rows. It failed
the unchanged 80-signal density gate, so no P&L was evaluated and no threshold
or window was relaxed.

Trial 478–482 then tested a first-session-of-month institutional-flow
lifecycle. SPY supplied only the observed exchange calendar; stocks had to
close above their frozen pivot, entered next open and exited three sessions
later. Density passed with 143 signals, but 99 train trades produced -0.32%
CAGR, -0.220 Sharpe, 0.750 PF and -0.56% trim-five expectancy. A/B/C/D were
7/7/0/0, normalized raw and final score 17/100 (Reject). The train gate failed,
so validation and best-available OOS stayed sealed.

Trial 483–488 tested a canonical 20-return lag-1 autocorrelation zero-cross as
an order-splitting persistence signal. It passed density with 129 signals and
produced 103 train trades, 1.29% CAGR, 0.499 Sharpe and PF 1.515. Removing the
five largest winners reversed PF to 0.715 and expectancy to -0.47%; t-stat was
0.78, PSR 77.9% and approximate DSR probability 0.08%. A/B/C/D were 7/10/4/14,
normalized raw 42 and final survivorship-capped score 20/100 (Reject).
Validation/OOS stayed sealed and the serial-dependence parameters are closed.

Trial 489–495 used only repository-cached SEC Company Facts to test a distinct
share-supply contraction proxy. Same-accession weighted-average shares,
diluted-before-basic priority, strict filed-before timing and 120-day freshness
covered 78/79 requested train symbols and emitted 114 signals. Its 100 trades
produced 0.69% CAGR, 0.291 Sharpe, PF 1.025 and -0.57% trim-five expectancy.
A/B/C/D were 7/7/4/6, normalized raw 29 and final survivorship-capped score
20/100 (Reject). No external data, validation or OOS was accessed.

Trial 496–504 translated the supplied strong-stock exit checklist into one
causal state machine: persistent SMA10/SMA20 support, then an abnormal down day
or dual-MA damage followed by a frozen-MA rejection / pre-damage swing-low
break. The outcome-free gate passed with 58 custom exits among 103 unchanged
detection-entry signals, but 88 train trades produced only 0.50% CAGR, 0.228
Sharpe, PF 0.982 and -0.87% trim-five expectancy. Only one activation was an
abnormal day and ten were failed-MA recoveries; 47 were swing-low breaks, so
the proposed character-change mechanism mostly collapsed into another weak
swing-low exit. A/B/C/D were 7/7/4/0, normalized raw 22 and final
survivorship-capped score 20/100 (Reject). Validation and OOS stayed sealed.
The frozen rule, causal implementation, tests and complete signal/trade/equity
artifacts are under
[`backtests/character_change_exit_v2/`](backtests/character_change_exit_v2/).

Trial 505–518 then tested the prespecified per-ticker 20-session positive
stock-minus-SPY divergence gate on the unchanged pullback strategy. The
outcome-free train audit found only 24 qualifying signals out of 34, below the
frozen minimum of 30, so the confirmatory family stopped before reading any
returns. Trial 519 subsequently opened every fold and sensitivity cell as an
explicitly post-density descriptive audit that cannot support `IMPROVES`.
Train performance worsened (CAGR 1.60% → 0.75%; qualifying-minus-rejected
matched excess -3.10 pp). Validation improved, but best-available OOS remained
economically negative: baseline CAGR -3.22% versus challenger -2.16%, while
qualifying baseline trades had -3.39% mean matched excess versus -1.45% for
rejected trades. OOS divergence/excess Spearman was -0.079, both strategies
lost more at stressed costs, and the capped diagnostic score was 14/100. Final
verdict: **INCONCLUSIVE**. See
[`backtests/relative_divergence_v2/results/relative_divergence_2026-08-02_111455.md`](backtests/relative_divergence_v2/results/relative_divergence_2026-08-02_111455.md).

Trial 520 tested one fixed medium-term trend gate: signal-date close strictly
above SMA50 and SMA50 strictly above its value 20 stock sessions earlier. It
retained 86.1% of best-available OOS signals and reduced the frozen baseline's
loss from -3.22% to -2.81% CAGR, but did not create a positive strategy. Train
CAGR fell from 1.60% to 1.36%, validation remained 1.14%, OOS Sharpe was
-0.725, PF 0.621 and drop-best-five expectancy -3.22%. OOS CAGR remained
negative at 2x/5x/10x costs, and the 2024 result worsened materially. Final
verdict: **INCONCLUSIVE / practical reject**, Backtest Score 14/100. See
[`backtests/ma50_slope_v2/results/ma50_slope_2026-08-02_125453.md`](backtests/ma50_slope_v2/results/ma50_slope_2026-08-02_125453.md).

Trial 521 then tested the intended market-relative version: stock and SPY
MA50 percentage slopes over 20 aligned common sessions, requiring positive
stock slope, stock slope above SPY slope and stock close above SMA50. It
retained 71.1% of OOS signals and reduced CAGR loss from -3.22% to -2.89%, but
qualifying baseline trades underperformed rejected trades by 1.24 points of
matched-SPY excess. OOS Sharpe was -0.787, PF 0.541, mean excess -3.44% with
95% CI [-4.99%, -1.78%], and drop-best-five expectancy -3.92%. All cost-stress
cells and displayed OOS years remained negative. Verdict: **INCONCLUSIVE /
practical reject**, score 14/100. See
[`backtests/relative_ma50_slope_v2/results/relative_ma50_slope_2026-08-02_132450.md`](backtests/relative_ma50_slope_v2/results/relative_ma50_slope_2026-08-02_132450.md).

Trial 522–541 exhaustively displayed the requested MA10–MA200 grid in steps of
10 while keeping the relative-slope window fixed at 20. No cell passed all
five frozen train gates, so validation and OOS remained sealed. MA60 had the
highest raw train CAGR at 1.95%, but only 17 trades and -0.45% drop-best-five
expectancy; adjacent cells were materially weaker. Among cells with at least
20 trades, MA20 led exposure-excess but returned only 1.13% CAGR versus 1.60%
baseline, had -1.34 pp pass-minus-fail matched excess and -2.12% trimmed
expectancy. Family verdict: **NO_QUALIFYING_WINNER**; diagnostic score 45/100
raw and 20/100 capped. See
[`backtests/relative_ma_grid_v2/results/relative_ma_grid_2026-08-02_133338.md`](backtests/relative_ma_grid_v2/results/relative_ma_grid_2026-08-02_133338.md).

Trial 542 removed VCP detection, breakout and the MA20 pullback entirely, then
used the requested relative-MA60 condition as a standalone false-to-true entry.
The apparent 21.17% train CAGR collapsed to 6.27% in validation and 4.88% in
best-available OOS, versus 22.87% and 12.05% for SPY. Full CAGR was 7.59%
versus 15.51% for SPY, with -5.99% exposure-matched excess CAGR. The latest
305 trades had PF 1.222, -0.03% drop-best-five expectancy and lost money at
5x costs. Verdict: **WORSENS**, raw score 55/100 and final survivorship-capped
score 20/100. See
[`backtests/ma60_only_v2/results/ma60_only_2026-08-02_161116.md`](backtests/ma60_only_v2/results/ma60_only_2026-08-02_161116.md).

Trial 543 removed that standalone strategy's 60-session timeout and replaced
it with a causal 8% completed-close trailing stop. It sharply worsened the
latest result: CAGR fell 4.88% → -6.37%, MDD widened -25.52% → -35.39%, PF
fell 1.222 → 0.797 and drop-best-five expectancy fell to -1.55%. The trail
reduced average loss but cut average winners 16.12% → 9.80%, lowered win rate
37.7% → 31.1%, and generated more whipsaw trades. Full CAGR fell 7.59% →
-0.66%. Verdict: **WORSENS**, Backtest Score 19/100. See
[`backtests/ma60_trailing_v2/results/ma60_trailing_2026-08-02_163423.md`](backtests/ma60_trailing_v2/results/ma60_trailing_2026-08-02_163423.md).

Trial 544 kept the same standalone entry and 8% initial hard stop, but removed
the timeout and switched to a causal 24% completed-close trailing stop only
after a close reached +3R. Best-available OOS CAGR improved 4.88% → 6.22%, MDD
improved -25.52% → -23.12%, and 5x-cost CAGR remained +3.63%. However, only
31/99 OOS trades armed the trail, average holding time rose to 112 sessions,
and removing the best five trades changed expectancy to -1.61%. The portfolio
still trailed SPY by 5.57 points of exposure-matched CAGR. Verdict:
**INCONCLUSIVE**, score 20/100. See
[`backtests/ma60_3r_trailing_v2/verification_report.md`](backtests/ma60_3r_trailing_v2/verification_report.md).

Trial 545–550 kept that exit frozen and searched standalone MA10/20/30/40/50/60
entries on train only. MA40, MA50 and MA60 passed the six train gates; MA60
retained the highest exposure-matched excess CAGR (+2.48%) and was selected.
It then failed validation: CAGR was 6.72% versus SPY 22.87%, exposure-matched
excess CAGR was -11.04%, and MDD was -32.96%. Best-available OOS therefore
remained sealed. Family verdict: **VALIDATION_FAIL**, score 20/100. See
[`backtests/ma10_60_3r_trailing_grid_v2/verification_report.md`](backtests/ma10_60_3r_trailing_grid_v2/verification_report.md).

Trial 551–568 applied 18 user-supplied entry-date windows to the unchanged
MA60/+3R exit strategy. Only seven windows overlap executable 2016+ periods.
On best-available OOS, raw CAGR rose 6.22% → 10.08% and MDD improved -23.12%
→ -14.17%, but exposure-matched excess CAGR worsened -5.57% → -7.32% and
mean matched-SPY trade excess was -10.13% (95% CI [-18.29%, -1.64%]). Full
CAGR was effectively unchanged, 9.71% → 9.76%. Because the dates' causal
provenance is unknown, verdict: **DESCRIPTIVE_ONLY / diagnostic INCONCLUSIVE**,
score 20/100. See
[`backtests/ma60_period_gate_v2/verification_report.md`](backtests/ma60_period_gate_v2/verification_report.md).

Trial 569–572 kept MA60, those calendar windows and the current exit fixed,
then tested 10/20/30/40-session slope windows sequentially. The 10-session
cell led train at 19.21% CAGR and +7.44% exposure-matched excess CAGR, but only
18 trades made the estimate thin. In validation it returned 13.53% CAGR while
exposure-matched excess CAGR fell to -6.93% and drop-best-five expectancy to
-1.08%. It failed two frozen gates, so OOS stayed sealed. Outcome:
**VALIDATION_FAIL / DESCRIPTIVE_ONLY**, score 20/100. See
[`backtests/ma60_slope_grid_period_gate_v2/verification_report.md`](backtests/ma60_slope_grid_period_gate_v2/verification_report.md).

At the user's explicit direction after that validation failure, the **current
research candidate** now uses a 10-session MA60 slope window. Frozen Trial
542/544/551 code remains at 20 sessions for reproducibility. The override is
implemented in [`scripts/current_ma60_candidate.py`](scripts/current_ma60_candidate.py)
and documented in [`docs/current_ma60_candidate.md`](docs/current_ma60_candidate.md).
It also forces existing positions out at the first ticker open outside all
supplied calendar windows; finite endpoints remain inclusive and the final
2025-04-07 window remains open-ended. It remains experimental and must not be
described as validated or deployable.

The regenerated Trial 573 descriptive report returned 19.71% train CAGR,
16.61% validation CAGR, 15.34% contaminated best-available OOS CAGR and 16.39%
full CAGR. Full exposure-matched excess CAGR was -2.96%, while validation was
-9.24% and contaminated OOS was -3.70%. The normalized raw score was 82, but
incomplete survivorship coverage and the absence of untouched OOS hard-capped
the final score at **20/100 (Reject)**. See
[`backtests/current_ma60_candidate_v2/results/current_ma60_candidate_2026-08-02_192559.md`](backtests/current_ma60_candidate_v2/results/current_ma60_candidate_2026-08-02_192559.md).

Trial 574 removed only the forced `period_exit`. Contaminated OOS CAGR fell
15.34% → 12.27%, MDD worsened -10.81% → -14.60%, and Sharpe fell 1.124 →
0.869. Full CAGR fell 16.39% → 15.16% and MDD worsened -18.80% → -27.24%.
Positions stayed open much longer and occupied scarce portfolio slots; the
ablation therefore supports retaining `period_exit` as a portfolio-risk and
capital-recycling rule, but remains post-hoc and non-validating. See
[`backtests/current_ma60_candidate_no_period_exit_v2/comparison_with_period_exit_2026-08-02.md`](backtests/current_ma60_candidate_no_period_exit_v2/comparison_with_period_exit_2026-08-02.md).

Source audit then confirmed that the periods are the actual next-open IN/OUT
states from the independently maintained `qqq_backtest.py` breadth strategy.
Trial 575 synchronized stock exits with each QQQ exit-date open instead of
waiting one extra session. Against a no-QQQ-regime control, synchronized CAGR
improved 17.76% → 20.08% train, 12.22% → 18.97% validation, 11.01% → 15.66%
contaminated OOS and 14.46% → 17.33% full; MDD improved in all four partitions.
Exposure-matched excess remained negative outside train, so this is a useful
market-timing/risk overlay, not evidence of stock-selection alpha. See
[`backtests/qqq_synchronized_regime_v2/source_and_overlay_report.md`](backtests/qqq_synchronized_regime_v2/source_and_overlay_report.md).

The replay also found and fixed a historical benchmark-alignment defect.
Stocks with short or gapped histories had previously selected SPY by the
stock's integer bar offset, which could use a benchmark observation after the
stock's as-of date. Historical screening now selects the latest SPY session
on or before the stock as-of date, and regression tests enforce that causal
contract. This invalidates the old Trial 288 coefficients and its previously
reported 5.58% result; a date-aligned reconstruction of the old 2020–2021
window returned 4.82% CAGR and failed the top-five-winner trim.

The 2022–2026 replay is explicitly **exploratory, not untouched OOS**. Existing
membership coverage is 91.31% and delisted coverage remains incomplete. The
frozen specification, complete verification, metrics and reproduction
commands are committed at:

- [`backtests/exploratory_existing_data_replay/frozen_spec.md`](backtests/exploratory_existing_data_replay/frozen_spec.md)
- [`backtests/exploratory_existing_data_replay/results/verification_report.md`](backtests/exploratory_existing_data_replay/results/verification_report.md)
- [`backtests/exploratory_existing_data_replay/results/verification_metrics.json`](backtests/exploratory_existing_data_replay/results/verification_metrics.json)
- [`backtests/v2_research_commands.md`](backtests/v2_research_commands.md)

The current success definition uses repository-local 2006+ data only and does
not search or require 2000–2005 PIT. It requires the same frozen strategy to
produce at least 20% net CAGR and 30 independent trades on a pre-frozen
best-available OOS, with the Backtest Score fully calculated under the A/B/C/D
rubric and every survivorship/contamination cap disclosed. There is no minimum
score threshold, but a cap may not be hidden, waived or bypassed. The data
inventory and frozen chronology are in
[`backtests/current_2006_plus_data_audit/inventory.md`](backtests/current_2006_plus_data_audit/inventory.md).

### Daily MA60 strategy dashboard

`scripts/run_daily_ma60_strategy.py` is the daily research runner for the
current MA60/Slope10 plus synchronized QQQ regime candidate. On its first run
it copies the local PIT seed into ignored `daily_data/`; subsequent runs
refresh the latest current-S&P-500 and real-SPY OHLCV tail from Yahoo Finance,
write `latest_prices.csv` plus a dated snapshot, query the sibling
`spy500-breadth-backtest/qqq_backtest.py` state machine, and print metrics,
recent trades, open positions and causal next-open candidates.

```bash
.venv/bin/python scripts/run_daily_ma60_strategy.py
```

Useful diagnostics:

```bash
# Reuse saved prices without contacting Yahoo
.venv/bin/python scripts/run_daily_ma60_strategy.py --no-fetch

# Print every completed trade instead of the latest 20
.venv/bin/python scripts/run_daily_ma60_strategy.py --no-fetch --all-trades

# Override QQQ only when debugging an unavailable sibling repository
.venv/bin/python scripts/run_daily_ma60_strategy.py --no-fetch --force-qqq-state in
```

The script never treats an unfinished US daily bar as a signal bar; a close
confirmed on day *t* is labelled only for the next eligible open. It is a
paper/research dashboard, not broker execution. New buys are blocked whenever
the QQQ breadth date lags the stock-price date, and the QQQ bridge is truncated
to the last completed stock session before its state is evaluated. The
underlying candidate remains validation-failed with a Backtest Score of 20/100
(Reject).

Roughly 1,500 simulated trades across S&P 500 and Russell 2000, 2016–2026,
with fold splits, outlier trims, cost sweeps and cross-universe replication.
The honest summary:

**The pattern itself carries no market-relative alpha.** Mean excess vs SPY
is statistically zero (or negative after costs) on every dataset — point-in-time
S&P +0.04%/trade (t 0.05), offline-CSV S&P −0.53%, Russell 2000 −0.45%
(−1.05%, t −2.11 at 30 bps costs). The headline raw-return significance is
market beta, not stock selection. Rescue attempts that all failed: detection
gates (trend/RS/score/volume), a 108-combo parameter grid, a hard
trend-template prerequisite, switching to small caps, the M.E.T.A. multi-edge
framework, and every exit family below. Treat the screener as a **candidate
list generator, not a buy signal**.

**Exits: the boring baseline wins.** Initial hard stop at
max(final-contraction low, entry −8%) plus a 60-bar time exit was never
robustly beaten: 8–45% trails, ATR×2–5 trails, profit targets (15–25%, 4R),
MA10/20/50-break "sell into weakness" (significantly harmful on small caps),
the strict 3-tier scale-out framework, laggard-culling and winner-riding all
land at zero or worse ([`exit_experiment.py`](scripts/exit_experiment.py),
[`exit_stress_experiments.py`](scripts/exit_stress_experiments.py)). Removing
the time exit turns the ledger into a survivorship lottery.

**Two execution-layer findings did survive validation** (both time folds,
outlier trims, cross-universe direction):

1. **MA20 pullback entry** — don't chase the breakout close; wait up to 15
   bars for the first low-touches-MA20-and-close-holds bar. +1.36 pp paired
   vs breakout entry on the same patterns (t 3.13, S&P; +2.18 pp, t 1.96 on
   R2K). The parameter surface is a smooth gradient (deeper MAs stronger,
   longer windows weaker), not a cliff
   ([`pullback_experiment.py`](scripts/pullback_experiment.py),
   [`pullback_sensitivity.py`](scripts/pullback_sensitivity.py)).
2. **Edge Rank position sizing** — a validated RS+extension cross-sectional
   score used as a size tilt (+1.01%/trade vs equal weight under practical
   constraints on the PIT dataset; universe/benchmark-sensitive, so weaker
   evidence than #1) ([`edge_rank.py`](scripts/edge_rank.py)).

Both ship with every live screen — see the Quick Scan columns below.

**Beyond VCP: the signal-family test.** Three prespecified non-VCP entry
families were run on the same infrastructure (one parameterisation each, no
grids) to ask whether this tape contains any harvestable signal at all
([`signal_family_experiment.py`](scripts/signal_family_experiment.py)).
Gross of frictions, 12-1 cross-sectional momentum looked like the winner
(S&P +0.89%/mo, monthly-clustered t 3.76, fold-stable; R2K +0.81%/mo vs an
equal-weight small-cap benchmark, t 3.13); 52-week-high proximity dies
post-2021 in both universes (a third independent null for breakout-style
entries) and RSI(2) mean-reversion is too thin to survive costs. The
validation suite ([`momentum_validation.py`](scripts/momentum_validation.py))
then measured turnover (~28%/month replaced; survives a 50 bp round-trip
easily), scanned lookbacks (smooth 3-1…12-1 surface) — and applied
**point-in-time index membership, which cut the edge ~60% in both
universes**: S&P +0.88 → +0.35%/mo (t 1.79), R2K +0.81 → +0.31%/mo (t 1.23),
using `scripts/data/r2k_membership.csv` (7,079 intervals rebuilt from
quarterly IWM holdings snapshots by
[`fetch_r2k_membership.py`](scripts/fetch_r2k_membership.py)). Most of the
measured "momentum edge" was the index-inclusion effect. PIT-clean momentum
is directionally positive but statistically insignificant on survivor-only
prices — **not deployable on this evidence either**.

**Close-out (2026-07-12).** Three final declared tests shut the remaining
doors. (1) Market-regime conditioning of trade excess — SPY>200DMA and SPY
20-day realized-vol splits — is null on both universes (|Welch t| ≤ 0.83),
as the breadth gate already was; the excess-vs-SPY metric is market-neutral
by construction, so regime gates structurally can't rescue it. (2) The two
validated overlays **don't stack**: the pullback improvement does not
concentrate in high-Edge names (Edge≥70 pooled t 1.09, outlier-driven;
interaction sign flips across universes) — they repair overlapping
weaknesses ([`edge_pullback_interaction.py`](scripts/edge_pullback_interaction.py)).
(3) The frozen v1 realistic portfolio scored **20/100 — Reject** (CAGR
−0.45%, exposure-matched excess t ≈ −1.8 to −2.7, OOS Sharpe collapse; see
`backtests/improved/final_verification_report.md`). **The research programme
is closed**: the execution findings are real, the alpha is not, and any v2
requires new data and a new predeclared hypothesis.

**Post-close-out declared test (2026-07-14): support-aware screening +
industry momentum — also null.** One frozen hypothesis was run on top of the
new support/resistance overlay: take only VCP detections within 3% of a
strong support zone, then keep only names whose GICS industry is in the top
30% by 6-1 momentum (t−126 → t−21, equal-weighted, thresholds hard-coded so
the test couldn't be tuned;
[`industry_momentum_vcp_experiment.py`](scripts/industry_momentum_vcp_experiment.py)).
The gate cut trades 104 → 48 and both variants still lose in the 2021–2026
fold; exposure-matched excess t −0.48 (gated) / −0.69 (support-only), OOS
Sharpe negative for both. GICS classification is a current snapshot, not
point-in-time, so even these numbers are optimistic. Conclusion unchanged:
support/resistance zones are a **context overlay, not an alpha source**.

## Install

```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r requirements.txt
```

The examples below use `python3` for readability. For exact reproduction, use
`.venv/bin/python` and the commands saved in
[`backtests/v2_research_commands.md`](backtests/v2_research_commands.md).

## 1. Screen for VCPs (today)

```bash
# Default: S&P 500, top 100 candidates
python3 scripts/screen_vcp.py --output-dir reports/

# Russell 2000 small-caps
python3 scripts/screen_vcp.py --index russell2000 --output-dir reports/

# S&P 500 + Russell 2000 combined (no candidate cap; slower)
python3 scripts/screen_vcp.py --index both --full-universe --output-dir reports/

# Custom universe
python3 scripts/screen_vcp.py --universe AAPL NVDA MSFT AMZN META --output-dir reports/

# Minervini strict mode: only valid VCPs in Pre-breakout/Breakout state
python3 scripts/screen_vcp.py --strict --output-dir reports/
```

Pipeline: **Pre-Filter** (price/volume/52w position) → **Trend Template**
(7-point Stage 2 filter) → **VCP Detection & Scoring** (contraction analysis,
volume dry-up, pivot proximity, relative strength).

Outputs timestamped `vcp_screener_*.json` and `vcp_screener_*.md` reports.

Every candidate row carries the two validated execution overlays:

| Quick Scan column | Meaning |
|---|---|
| **Edge** | Edge Rank v2 — cross-sectional 12m-RS + inverse-extension percentile within today's candidates |
| **Weight** | Suggested position size (skip Edge<30, linear in Edge, capped at 1.5× mean) |
| **Support / Resistance** | Nearest active zone bounds and signed distance to its midpoint |
| **R/R** | Simple reward/risk from the nearest resistance and support midpoints; blank if either side is unavailable |
| **Entry** | MA20 pullback-entry state: `await BO` → `wait PB n/15` → **`BUY ZONE`** (today is the touch-and-hold bar) → `PB done` / `missed` / `invalid` |

### Support and resistance zones

Support and resistance are **probabilistic price zones, not guaranteed reversal
points or trading signals**. Zone enrichment is on by default for live,
historical and backtest scans. It is an additive overlay: it does not change the
existing VCP score or ranking unless you explicitly enable a support/resistance
filter.

#### Detection and look-ahead prevention

- The calculator works on a chronological copy of the daily OHLCV bars. A
  strict swing high/low needs `--sr-swing-window` lower highs/lows on both
  sides, so with the default window of 5 a swing becomes available only five
  sessions after the extreme. Historical scans never backdate that knowledge.
- Candidate points include confirmed swings, prior major highs/lows, sparse
  rolling consolidation boundaries, causally confirmed VCP contraction
  boundaries, and the three highest-volume daily closes whose volume is at
  least 1.5× the prior rolling 50-session average. The latter are a deliberately
  coarse volume-at-price proxy. Points with the same role are clustered when
  they are within
  `max(price × --sr-zone-tolerance-pct, ATR × --sr-zone-tolerance-atr)`; the
  defaults are `max(0.5% of price, 0.5 × ATR(14))`.
- Touch reaction statistics use only the following bars needed to confirm the
  swing. A zone is not searched for a break until the configured minimum
  number of touches is confirmed. Later touches update the bounds with their
  own contemporaneous ATR tolerance without rewriting an earlier event. A
  breakout is recognized only on its final confirmation close, and a
  role-reversal retest only on a later bar.
- By default, a returned zone needs at least two distinct touch dates, at least
  moderate strength, and only the nearest three active zones on either side are
  included in `support_zones`, `resistance_zones` and `zones`. `all_zones`
  retains scored zones that passed the minimum-touch rule, including zones
  below the displayed strength threshold.

Distances are signed midpoint distances from the current close: support below
price is normally negative and resistance above price positive. Potential
reward/risk is `(resistance midpoint - price) / (price - support midpoint)`;
it is `null` when either side is missing or the geometry is invalid.

#### Transparent strength score

Each zone exposes `strength_score` (0–100) and every term in
`strength_components`. The score is the capped sum:

```text
touches        = min(30, confirmed_touches / 4 × 30)
recency        = 15 × max(0, 1 - bars_since_latest_confirmation / (lookback_bars - 1))
reaction       = 20 × min(1, average_reaction_in_ATR / 3)
volume         = 10 × min(1, average_touch_volume_ratio / 1.5)
time_near_zone = 10 × min(1, closes_inside_zone / 10)
major_swing    = 10 if any contributing point is a major swing, else 0
role_reversal  = 5 if a confirmed role reversal occurred, else 0
```

Categories are **weak** `<35`, **moderate** `35–59.99`, **strong** `60–79.99`
and **very strong** `80–100`.

#### Breakouts and role reversal

Only closes count. A resistance break requires a close above the zone upper
bound plus `--sr-breakout-min-distance-pct`; a support break uses the
corresponding close below the lower bound. Intraday wicks do not increment the
counter, and a failed close resets it. Require consecutive confirming closes
with `--sr-breakout-confirmation-closes`. Add
`--sr-require-breakout-volume` to require every confirming bar to meet
`--sr-breakout-volume-multiplier` times its rolling 50-session average volume.

After the final confirming close, the first later bar that tests the old zone
and closes within it or on its new side marks resistance-turned-support or
support-turned-resistance; the close need not clear the zone's far edge.
Disable this with `--sr-no-role-reversal`. A retest filter refers to a retest
on the current scan bar; the persistent
`role_reversal_detected` field reports any detected reversal in the retained
history.

#### VCP interpretation and JSON output

The overlay adds the requested flat fields (`nearest_support_*`,
`nearest_resistance_*`, distances, strength, reward/risk, inside-zone and
break/breakdown flags) plus a complete nested `support_resistance` object. Its
explainable VCP signals are:

- `pivot_matches_resistance_zone` — the pivot falls in or within the fixed 1%
  margin around a resistance zone.
- `breakout_above_resistance` — price is above the close-confirmed broken
  resistance zone aligned with the VCP pivot.
- `retest_of_breakout_zone` — the current bar retests resistance now acting as
  support.
- `last_contraction_support` — active support nearest the final contraction
  low.
- `base_support_zone` — the highest-scoring active support zone.
- `distance_from_vcp_pivot_pct` — signed current-close distance from the VCP
  pivot.
- `pivot_resistance_distance_pct` — absolute distance from the pivot to the
  closest resistance-zone midpoint.
- `breakout_volume_confirmed` — the existing VCP volume calculator confirmed
  breakout expansion.
- `breakout_holds_above_zone` — current price remains above a close-confirmed
  broken resistance zone.

This repository has no chart frontend. JSON reports are chart-ready: zone
objects contain bounds, midpoint, role, touch/confirmation dates, strength and
role-reversal metadata, while `chart_markers` supplies the latest price, VCP
pivot and confirmed breakout point. An abridged result (generated from
deterministic daily bars) looks like:

```json
{
  "nearest_support": 96.45,
  "nearest_support_lower": 95.85,
  "nearest_support_upper": 97.05,
  "nearest_support_strength": "strong",
  "support_distance_pct": -4.47,
  "nearest_resistance": 106.75,
  "nearest_resistance_lower": 105.35,
  "nearest_resistance_upper": 108.15,
  "nearest_resistance_strength": "very_strong",
  "resistance_distance_pct": 5.73,
  "reward_risk_ratio": 1.28,
  "pivot_matches_resistance_zone": true,
  "pivot_resistance_distance_pct": 0.05,
  "breakout_above_resistance": false,
  "support_resistance": {
    "status": "ok",
    "zones": [
      {
        "type": "resistance",
        "lower": 105.35,
        "upper": 108.15,
        "midpoint": 106.75,
        "touches": 10,
        "strength_score": 88.11,
        "strength": "very_strong",
        "strength_components": {
          "touches": 30.0,
          "recency": 11.35,
          "reaction": 20.0,
          "volume": 6.76,
          "time_near_zone": 10.0,
          "major_swing": 10.0,
          "role_reversal": 0.0
        }
      }
    ],
    "chart_markers": {
      "latest_price": {"price": 100.96, "date": "2025-09-09"},
      "vcp_pivot": {"price": 108.0, "date": null},
      "breakout_point": null
    }
  }
}
```

#### Configuration and optional filters

The ratio-valued tolerance and breakout-distance options use decimal fractions
(`0.005` = 0.5%); filter distances use percentage points (`3` = 3%). These
options are shared by `screen_vcp.py` and `backtest_vcp.py`:

| CLI option | Default | Effect |
|---|---:|---|
| `--no-support-resistance` | off | Disable enrichment; default `enabled` is `true` |
| `--sr-swing-window` | `5` | Bars required on each side of a strict swing |
| `--sr-lookback-period` | `252` | Daily bars retained for zone analysis |
| `--sr-atr-period` | `14` | ATR averaging period |
| `--sr-zone-tolerance-pct` | `0.005` | Decimal price tolerance used for clustering |
| `--sr-zone-tolerance-atr` | `0.5` | ATR multiple used for clustering |
| `--sr-minimum-touches` | `2` | Minimum distinct touch dates |
| `--sr-breakout-confirmation-closes` | `1` | Required consecutive closes beyond a zone |
| `--sr-breakout-min-distance-pct` | `0.0` | Decimal minimum close distance beyond a zone |
| `--sr-breakout-volume-multiplier` | `1.2` | Required multiple of rolling 50-session volume when volume confirmation is enabled |
| `--sr-require-breakout-volume` | off | Enable breakout-volume confirmation |
| `--sr-no-role-reversal` | off | Disable role reversals; default `role_reversal_enabled` is `true` |
| `--sr-max-support-zones` | `3` | Maximum nearest active support zones returned |
| `--sr-max-resistance-zones` | `3` | Maximum nearest active resistance zones returned |
| `--sr-minimum-zone-strength` | `moderate` | Minimum returned strength: `weak`, `moderate`, `strong`, or `very_strong` |

The serialized config also records `pivot_zone_tolerance_pct: 0.01` (1%) for
VCP pivot matching. This value currently has no CLI override.

All filters are inactive by default and combine with AND when multiple flags
are supplied:

| Optional filter | Keeps candidates where… |
|---|---|
| `--sr-near-support-pct X` | Absolute distance to the support midpoint is at most `X` percentage points and support is strong by default; use `--sr-min-support-strength very_strong` to raise the requirement |
| `--sr-below-resistance-pct X` | Resistance midpoint is 0 to `X` percentage points above price |
| `--sr-breaking-above-resistance` | A strong-or-better resistance break is confirmed and price remains above that zone |
| `--sr-retesting-former-resistance` | The current bar retests confirmed former resistance as support |
| `--sr-min-support-strength LEVEL` | Nearest support is at least `weak`, `moderate`, `strong`, or `very_strong` |
| `--sr-min-resistance-strength LEVEL` | Nearest resistance is at least the selected category |
| `--sr-min-reward-risk-ratio RATIO` | Midpoint reward/risk is at least `RATIO` |
| `--sr-pivot-near-resistance-pct X` | VCP pivot is within `X` percentage points of the closest resistance-zone midpoint |
| `--sr-vcp-breakout-above-resistance` | The VCP candidate is above a confirmed broken resistance zone |

For example, require two closes at least 1% beyond a zone with 1.5× volume:

```bash
python3 scripts/screen_vcp.py --universe AAPL MSFT \
  --sr-breakout-confirmation-closes 2 \
  --sr-breakout-min-distance-pct 0.01 \
  --sr-require-breakout-volume --sr-breakout-volume-multiplier 1.5 \
  --output-dir reports/
```

Or screen within 3% of strong support with at least 1.5 midpoint reward/risk:

```bash
python3 scripts/screen_vcp.py --universe AAPL MSFT \
  --sr-near-support-pct 3 --sr-min-support-strength strong \
  --sr-min-reward-risk-ratio 1.5 --output-dir reports/
```

#### Limitations

- Detection uses daily OHLCV, not intraday or tick data. Besides relative daily
  volume around touches, it admits at most three ≥1.5×-volume daily closes as a
  coarse price proxy; this is not a tick-level volume profile or a true
  volume-profile node calculation.
- Yahoo mode and the backtest's `--csv-data` path use raw, unadjusted OHLC, so
  splits and other corporate actions can create artificial gaps or zones. The
  backtest's `--price-csv` path scales OHLC using `Adj Close`, but still depends
  on the source's adjustment quality.
- New listings, sparse histories and invalid/missing candles can produce
  `insufficient_data`, `no_zones` or `null` nearest-zone fields. A default swing
  alone needs 11 valid sessions; stable multi-touch zones usually need much
  more history.
- Zone discovery and scoring add work per evaluated symbol and historical
  cursor. Large-universe/backtest runs can be slower; use
  `--no-support-resistance` when the overlay is not needed, or reduce
  `--sr-lookback-period` after validating the trade-off.
- Strength and midpoint reward/risk are explainable heuristics, not calibrated
  reversal probabilities. Reward/risk ignores fills, slippage, gaps, costs and
  the probability of reaching either zone.

## 2. Historical scan (one ticker)

Walk a single ticker's history and find every VCP that ever formed, each
labeled with its forward outcome:

```bash
# 10 years of NVDA (2520 trading days)
python3 scripts/screen_vcp.py --history 2520 --ticker NVDA --output-dir reports/
```

## 3. Backtest (multi-ticker, 10 years)

Run the historical scanner across a whole universe and aggregate the results
into portfolio-level statistics — overall breakout/stop/timeout rates, plus
breakdowns by year, by composite-score rating band, and by ticker:

```bash
# 10-year backtest on a custom universe
python3 scripts/backtest_vcp.py --years 10 --universe AAPL NVDA MSFT AVGO LLY

# 10-year backtest on the first 50 S&P 500 snapshot names
python3 scripts/backtest_vcp.py --years 10 --index sp500 --limit 50

# Full S&P 500 (slow: ~500 history downloads)
python3 scripts/backtest_vcp.py --years 10 --index sp500 --limit 0

# Tickers from a file (one per line, '#' comments allowed)
python3 scripts/backtest_vcp.py --years 10 --universe-file tickers.txt
```

Outputs timestamped `vcp_backtest_*.json` (full detection timelines included)
and `vcp_backtest_*.md` into `backtests/`.

### Survivorship-aware universe (recommended)

Backtesting today's index members over the past is survivorship bias. Build a
point-in-time universe instead — every ticker that was an S&P 500 member at
any point in the window, including departed/delisted names:

```bash
python3 scripts/fetch_historical_members.py \
  --start 2016-07-08 --end 2026-07-08 \
  --emit-universe backtests/universe_pit_2016_2026.txt

python3 scripts/backtest_vcp.py --years 10 \
  --universe-file backtests/universe_pit_2016_2026.txt
```

Note: Yahoo has no data for many delisted tickers — those are logged as
failed/skipped, so residual survivorship bias remains (fully eliminating it
requires a survivorship-bias-free dataset like CRSP or Norgate).

## 4. Trade simulation (excess-over-SPY)

Convert a backtest's detections into Minervini-style trades and report
**excess return over SPY (same holding windows) as the primary metric**:

```bash
python3 scripts/trade_simulator.py backtests/vcp_backtest_<timestamp>.json \
  --membership-csv scripts/data/sp500_membership.csv
```

Trade rules: enter on the first close above the pivot, **skip fills more than
5% above the pivot** (`--max-extension-pct`), stop at
**max(contraction low, entry − 8%)** (`--max-risk-pct`), exit on a close below
the stop or after 60 bars (`--max-hold-bars`). The membership filter drops
detections made while the ticker was not an index member.

Outputs `vcp_trades_*.json/.md` with t-stats and bootstrap confidence
intervals for both raw and SPY-excess returns.

### Frozen portfolio validation

The pattern-level trade simulator does not model overlapping positions or a
daily-marked account. The frozen v1 validation adds conservative next-session
fills, MA20 pullback entries, causal Edge Rank sizing, cash/capacity/sector/ADV
constraints, and two-sided costs:

```bash
python3 scripts/portfolio_backtest.py backtests/csv_full/vcp_backtest_<ts>.json \
  --price-csv SP500_Historical_Data.csv --output-dir backtests/improved

python3 scripts/portfolio_robustness.py \
  backtests/improved/vcp_portfolio_<ts>_daily.csv \
  --return-column exposure_matched_excess_return --trials 180 \
  --iterations 5000 --block-size 10
```

The portfolio command emits JSON and a daily CSV containing raw, full-SPY,
and exposure-matched excess returns. Use `--commission-bps` and
`--slippage-bps` for cost stress tests. The rules and OOS contract are frozen
in [`references/frozen_strategy_v1.md`](references/frozen_strategy_v1.md).

The current v2 research path extends this engine without changing its fixed
portfolio allocation or risk model. Signals confirmed at a daily close may
fill no earlier than the next trading session; PIT membership is checked on
both signal and fill dates. The latest existing-data replay and its full
robustness suite can be reproduced from the final command block in
[`backtests/v2_research_commands.md`](backtests/v2_research_commands.md).

**Optional S&P 500 breadth gate (`--min-breadth`):** skips entries taken when
market breadth (% of S&P 500 above their 200-day MA, `scripts/data/sp500_breadth_daily.csv`)
on the entry date is below the given level. This is a **risk dial, not an alpha
source** — the [breadth experiment](scripts/breadth_experiment.py) found it does
not improve market-relative excess-over-SPY (any absolute-return effect was
concentrated in two crisis-rebound years). Use it only to trim absolute-drawdown
tail trades in weak tapes:

```bash
python3 scripts/trade_simulator.py backtests/vcp_backtest_<ts>.json \
  --membership-csv scripts/data/sp500_membership.csv --min-breadth 40
```

### Backtest caveats

- `trade_simulator.py` results are close-based with no slippage/commissions
  and no position-sizing/overlap handling — pattern-level evidence, not a
  full portfolio simulation. `portfolio_backtest.py` is the realistic
  daily-marked path and includes next-session fills, costs and constraints.
- Delisted tickers without Yahoo data drop out of the universe (partial
  survivorship bias; see above).
- Historical `marketCap` and universe-relative RS aren't reconstructable from
  OHLCV, so per-detection RS is vs SPY only.

## Tuning parameters

Both the screener and the backtest accept the same detection knobs:

| Parameter | Default | Effect |
|-----------|---------|--------|
| `--min-contractions` | 2 | Higher = fewer but higher-quality patterns |
| `--t1-depth-min` | 10.0% | Higher = excludes shallow first corrections |
| `--breakout-volume-ratio` | 1.5x | Higher = stricter volume confirmation |
| `--atr-multiplier` | 1.5 | Lower = more sensitive swing detection |
| `--contraction-ratio` | 0.70 | Lower = requires tighter contractions |
| `--min-contraction-days` | 5 | Higher = longer minimum contraction |
| `--lookback-days` | 120 | Longer = finds older patterns |

Backtest-specific: `--years` (default 10), `--stride-days` (as-of cursor step,
default 5), `--outcome-days` (forward window, default 60), `--limit`
(index-universe cap, default 50, `0` = all), `--sleep-secs` (fetch pacing).

## Offline mode

Backtest, trade-sim and every experiment can run without touching Yahoo by
supplying a long-format OHLCV CSV (`Ticker,Date,Open,High,Low,Close,Adj
Close,Volume`, ISO dates). Build one for the current S&P 500 snapshot with:

```bash
# Downloads max available daily history per ticker (batched, atomic replace)
python3 scripts/download_sp500_history.py                 # → SP500_Historical_Data.csv
python3 scripts/download_sp500_history.py --start 2016-01-01 --output data/sp500.csv
```

Then point the pipeline at it:

```bash
# Backtest from the local CSV (uses its SPY series as the benchmark)
python3 scripts/backtest_vcp.py --csv-data SP500_Historical_Data.csv --limit 0 --years 10

# Trade-sim / experiments take --price-csv
python3 scripts/trade_simulator.py backtests/vcp_backtest_<ts>.json \
  --price-csv SP500_Historical_Data.csv
```

Check `api_stats.data_source == "csv"` in the report metadata to confirm the
run really was offline. CSV universes are current-member snapshots, i.e.
survivorship-biased — results are an optimistic ceiling.

## Experiments

Each experiment is a standalone CLI over a `vcp_trades_*.json` (or
`vcp_backtest_*.json`) report; all support `--price-csv` for offline runs and
report excess-vs-SPY with t-stats and bootstrap CIs:

| Script | Question it answers |
|---|---|
| [`gate_experiment.py`](scripts/gate_experiment.py) | Do trend/RS-rank/score/volume entry gates add OOS excess? *(No)* |
| [`exit_experiment.py`](scripts/exit_experiment.py) | Do trailing/ATR/profit-target/MA-break exits beat stop+60d? *(No)* |
| [`exit_stress_experiments.py`](scripts/exit_stress_experiments.py) | Stop-only, strict 3-tier scale-out, asymmetric cull/ride? *(No — see docstring)* |
| [`meta_experiment.py`](scripts/meta_experiment.py) | Do M.E.T.A. multi-edge entry filters help? *(Regime luck, fails folds)* |
| [`pullback_experiment.py`](scripts/pullback_experiment.py) | Breakout entry vs waiting for the pullback? *(MA20 touch wins, +1.36 pp paired)* |
| [`pullback_sensitivity.py`](scripts/pullback_sensitivity.py) | Is the MA20 rule a cliff or a smooth surface? *(Smooth gradient; MA30 strongest)* |
| [`edge_rank.py`](scripts/edge_rank.py) | Cross-sectional Edge Rank IC, tilt backtest, deployable sizing |
| [`breadth_experiment.py`](scripts/breadth_experiment.py) | Does a market-breadth gate add alpha? *(Risk dial only)* |
| [`edge_pullback_interaction.py`](scripts/edge_pullback_interaction.py) | Do the two shipped overlays compound — does pullback Δ concentrate in high-Edge names? *(No — substitutes, not complements)* |
| [`grid_search.py`](scripts/grid_search.py) | Detection-parameter grid (108 combos; deflated Sharpe ≈ 0) |
| [`signal_family_experiment.py`](scripts/signal_family_experiment.py) | Any non-VCP signal in this tape? 12-1 momentum / RSI(2) mean-rev / 52w-high *(momentum only — until PIT)* |
| [`momentum_validation.py`](scripts/momentum_validation.py) | Momentum follow-ups: turnover+costs, PIT membership, lookbacks, vol scaling, R2K benchmark swap *(PIT cuts ~60% → +0.3%/mo, ns)* |
| [`industry_momentum_vcp_experiment.py`](scripts/industry_momentum_vcp_experiment.py) | Does a frozen 6-1 GICS industry-momentum gate rescue support-qualified VCPs? *(No — fewer trades, still negative OOS)* |
| [`daily_score_decay_discovery.py`](scripts/daily_score_decay_discovery.py) | Purged daily causal entry/exit research with fixed fit, calibration and later evaluation windows |
| [`character_change_exit_discovery.py`](scripts/character_change_exit_discovery.py) | Does a strong-trend → damage → failed-recovery/swing-low exit improve the unchanged detection entry? *(No — Trial 496–504 train reject)* |
| [`relative_divergence_experiment.py`](scripts/relative_divergence_experiment.py) | Does a strict positive 20-session stock-minus-SPY gate improve the frozen pullback strategy? *(Inconclusive — Trial 505–518 density reject; Trial 519 descriptive audit)* |
| [`ma50_slope_experiment.py`](scripts/ma50_slope_experiment.py) | Does close above a strictly rising SMA50 improve the frozen pullback strategy? *(Inconclusive / practical reject — Trial 520)* |
| [`relative_ma50_slope_experiment.py`](scripts/relative_ma50_slope_experiment.py) | Does a positive stock MA50 percentage slope above SPY's aligned MA50 slope improve the frozen pullback strategy? *(Inconclusive / practical reject — Trial 521)* |
| [`relative_ma_grid_experiment.py`](scripts/relative_ma_grid_experiment.py) | Train-only MA10–MA200 grid with fixed 20-session stock-versus-SPY slope logic and frozen sequential gates *(No qualifying winner — Trial 522–541)* |
| [`ma60_only_experiment.py`](scripts/ma60_only_experiment.py) | Standalone false-to-true relative-MA60 entry with no VCP/MA20/Edge Rank *(Worsens — Trial 542)* |
| [`ma60_trailing_experiment.py`](scripts/ma60_trailing_experiment.py) | Standalone relative-MA60 entry with timeout removed and causal 8% close-watermark trail *(Worsens — Trial 543)* |
| [`ma60_3r_trailing_experiment.py`](scripts/ma60_3r_trailing_experiment.py) | Standalone relative-MA60 entry with 8% hard stop until +3R, then causal 24% close-watermark trail and no timeout *(Inconclusive — Trial 544)* |
| [`ma10_60_3r_trailing_grid_experiment.py`](scripts/ma10_60_3r_trailing_grid_experiment.py) | Train-first standalone MA10–60 buy grid with the Trial 544 exit unchanged *(Validation fail — Trial 545–550)* |
| [`ma60_period_gate_experiment.py`](scripts/ma60_period_gate_experiment.py) | User-supplied fill-date windows on unchanged MA60/+3R strategy, with equal-clock comparison *(Descriptive only — Trial 551–568)* |
| [`ma60_slope_grid_period_gate_experiment.py`](scripts/ma60_slope_grid_period_gate_experiment.py) | Train-first 10/20/30/40-session MA60 slope grid inside the supplied calendar *(Validation fail / descriptive only — Trial 569–572)* |
| [`current_ma60_candidate.py`](scripts/current_ma60_candidate.py) | Canonical user-directed MA60/slope10 research override; preserves frozen 20-session trial implementations *(Validation failed; not deployable)* |
| [`current_ma60_candidate_backtest.py`](scripts/current_ma60_candidate_backtest.py) | Regenerates the current slope10 plus forced-period-exit report, cost stress, trade logs and equity curves *(Trial 573; descriptive only)* |
| [`exploratory_existing_data_verification.py`](scripts/exploratory_existing_data_verification.py) | Full Trial 288 replay audit: score, costs, folds, sensitivity, trims, bootstrap, PSR/DSR and causality |
| [`train_feasibility_audit.py`](scripts/train_feasibility_audit.py) | Determines whether a declared signal family clears its training gate before validation may be opened |
| [`fetch_r2k_membership.py`](scripts/fetch_r2k_membership.py) | Rebuild R2K PIT membership intervals from quarterly IWM holdings snapshots |
| [`build_trade_log_page.py`](scripts/build_trade_log_page.py) | Render trades JSONs into an interactive HTML ledger |

(The signal-family and momentum CLIs run straight off price data —
`--price-csv` or `--symbols-json` — rather than a trades JSON.)

## Refreshing index constituents

Membership snapshots live in `scripts/data/`. Refresh with:

```bash
python3 scripts/refresh_constituents.py --index both
```

## Tests

```bash
# Support/resistance unit and integration coverage
python3 -m pytest \
  tests/test_support_resistance_calculator.py \
  tests/test_support_resistance_integration.py -v

# Full suite
python3 -m pytest tests/ -v
```

Latest verified suite after the QQQ regime execution audit: **617 passed**.

## Docs

- `references/vcp_methodology.md` — VCP theory and the 7-point Trend Template
- `references/scoring_system.md` — composite scoring and rating bands
- `references/data_source.md` — yfinance data source and snapshot refresh
- `backtests/v2_research_commands.md` — exact v2 research and verification commands
- `backtests/exploratory_existing_data_replay/results/verification_report.md` — latest corrected replay verdict
- `backtests/character_change_exit_v2/frozen_spec.md` — latest frozen exit-family specification
- `backtests/character_change_exit_v2/results/character_change_exit_2026-08-02_002548.md` — Trial 496–504 verification report
- `backtests/relative_divergence_v2/results/relative_divergence_2026-08-02_111455.md` — Trial 505–519 verification report
- `backtests/ma50_slope_v2/results/ma50_slope_2026-08-02_125453.md` — Trial 520 verification report
- `backtests/relative_ma50_slope_v2/results/relative_ma50_slope_2026-08-02_132450.md` — Trial 521 verification report
- `backtests/relative_ma_grid_v2/results/relative_ma_grid_2026-08-02_133338.md` — Trial 522–541 grid report
- `backtests/ma60_only_v2/results/ma60_only_2026-08-02_161116.md` — Trial 542 standalone MA60-only report
- `backtests/ma60_trailing_v2/results/ma60_trailing_2026-08-02_163423.md` — Trial 543 standalone MA60 trailing-stop report
- `backtests/ma60_3r_trailing_v2/verification_report.md` — Trial 544 3R-armed 24% trailing-stop verification
- `backtests/ma10_60_3r_trailing_grid_v2/verification_report.md` — Trial 545–550 buy-period grid verification
- `backtests/ma60_period_gate_v2/verification_report.md` — Trial 551–568 calendar-gate verification
- `backtests/ma60_slope_grid_period_gate_v2/verification_report.md` — Trial 569–572 slope-window grid verification
- `docs/current_ma60_candidate.md` — current user-directed MA60/slope10 research configuration
- `backtests/current_ma60_candidate_v2/results/current_ma60_candidate_2026-08-02_192559.md` — Trial 573 regenerated current-candidate performance report
- `backtests/current_ma60_candidate_v2/results/current_ma60_candidate_2026-08-02_192559_zh-HK.md` — Trial 573 廣東話／繁體中文報告
- `backtests/current_ma60_candidate_no_period_exit_v2/results/current_ma60_candidate_no_period_exit_2026-08-02_202140.md` — Trial 574 no-period-exit ablation report
- `backtests/current_ma60_candidate_no_period_exit_v2/comparison_with_period_exit_2026-08-02.md` — with/without period-exit comparison
- `backtests/qqq_synchronized_regime_v2/source_and_overlay_report.md` — QQQ period provenance, execution audit and four-way overlay comparison
- `backtests/qqq_synchronized_regime_v2/results/current_ma60_candidate_qqq_synchronized_2026-08-02_203323.md` — Trial 575 synchronized QQQ overlay report

## Disclaimer

For research and education only. Nothing here is investment advice; past
pattern statistics do not predict future returns.
