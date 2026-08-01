# Current 2006+ Evidence-Boundary Audit — 2026-08-01

## Decision

The goal is **active, not complete, and not externally blocked**. Missing
2000–2005 PIT data is explicitly outside the current goal and must not be
searched, downloaded, reconstructed or required. The present failure is
strategy evidence: no frozen candidate has passed discovery, so validation and
best-available OOS remain sealed.

## Repository-local data boundary

The reproducible inventory is
`backtests/current_2006_plus_data_audit/inventory.{json,md}`.

- `SP500_PIT_2016_2026.csv`: 1,512,174 rows, 599 stocks plus real SPY,
  2014-01-02 through 2026-07-01, 91.31% measured 2016–2026 member-day
  coverage.
- `backtests/daily_rescreen_v2/SP500_PIT_through_2021.csv`: 934,273 rows,
  557 stocks plus real SPY, 2014-01-02 through 2021-12-31.
- `scripts/data/sp500_membership.csv`: 1,202 symbols / 1,255 intervals; 135
  priced symbols have at least one ended membership interval. This is
  historical-membership evidence, not proof that every such name delisted.
- The old 2006–2015 reconstruction has a preserved 69.74% coverage report but
  its raw price CSV is absent, so it cannot execute new rules. It remains
  contaminated prior-OOS evidence only.

The source CSVs contain 33 impossible OHLC envelopes. Thirty are HAR 2014
lookback bars; the remaining three are EVHC 2015, ANDV 2018 embargo and UA
2021 validation. Before any new return evaluation, the shared detector and
portfolio loader was repaired outcome-free: adjusted high/low are expanded to
contain adjusted open, close and the original range. Tests prove both clients
use the identical transform.

## Frozen chronology and contamination

| Partition | Dates | Evidence class |
|---|---|---|
| Discovery/train | 2016-07-01..2018-06-30 | heavily reused/mined |
| Embargo | 2018-07-01..2018-12-31 | no tuning or scoring |
| Validation | 2019-01-01..2021-12-31 | reused validation/internal holdout |
| Best-available frozen OOS | 2022-01-01..2026-03-31 | previously opened exploratory period; not untouched |

No period is genuinely untouched. A genuinely new signal may open the final
partition only after its unchanged rule passes train and validation. The final
report must disclose contamination, DSR/multiplicity and every applicable hard
cap. Conservatively, unresolved survivorship invokes cap 20 and the lack of a
genuine untouched OOS invokes cap 55; the lower applicable cap wins. These caps
are acceptable under the goal but cannot replace the CAGR/trade-count gates.

## Current strategy evidence

- Existing-data Trial 288 replay: 89 trades, 0.05% net CAGR, raw score 25,
  survivorship-capped score 20.
- Trial 352–357 anchored VWAP: 85 train trades, 1.62% CAGR, train fail.
- Trial 358–362 Chaikin Money Flow: 74 train trades, -0.23% CAGR, train fail.
- Trial 363–367 Wilder DMI crossover: 80 train trades, -0.80% CAGR, train
  fail; validation and best-available OOS not accessed.
- Trial 368–373 Parabolic SAR flip: 98 train trades, -0.86% CAGR, train fail;
  validation and best-available OOS not accessed.
- Trial 374–380 MACD crossover: 79 pre-portfolio signals versus the frozen
  minimum 80; rejected without return, validation or OOS access.
- Trial 381–386 Donchian channel: 79 pre-portfolio signals versus the unchanged
  minimum 80; rejected without return, validation or OOS access.
- Trial 387–393 ATR range expansion: 72 train trades, -0.63% CAGR, train fail;
  validation and best-available OOS not accessed.
- Trial 394–399 three-bar staircase: 144 train trades, -1.14% CAGR, train fail;
  validation and best-available OOS not accessed.
- Trial 400–405 repeated MA20 touch: 85 train trades, -1.82% CAGR, train fail;
  validation and best-available OOS not accessed.
- Trial 406–411 OBV accumulation: 90 train trades, -0.63% CAGR, train fail;
  validation and best-available OOS not accessed.
- Trial 412–417 slow cross-sectional momentum: 41 pre-portfolio signals versus
  the frozen minimum 80; rejected without return, validation or OOS access.
- Trial 418–424 log-price OLS trend quality: 79 train trades, 0.30% CAGR,
  0.138 Sharpe, PF 1.008 and -1.06% drop-top-five expectancy; train fail,
  validation and best-available OOS not accessed. Raw score 29, unresolved-
  survivorship-capped final score 20/100.
- Trial 425–431 Aroon extreme recency: 75 train trades, 0.08% CAGR, 0.040
  Sharpe, PF 1.022 and -1.10% drop-top-five expectancy; train fail, validation
  and best-available OOS not accessed. Raw score 24, unresolved-survivorship-
  capped final score 20/100.
- Trial 432–440 causal Ichimoku equilibrium: 81 train trades, -0.95% CAGR,
  -0.305 Sharpe, PF 0.868 and -1.65% drop-top-five expectancy; train fail,
  validation and best-available OOS not accessed. Raw/final score 17/100.
- Trial 441–447 realized semivariance asymmetry: 73 train trades, -0.03% CAGR,
  0.002 Sharpe, PF 1.120 and -1.09% drop-top-five expectancy; train fail,
  validation and best-available OOS not accessed. Raw score 28, unresolved-
  survivorship-capped final score 20/100.
- Trial 448–454 gap-adjusted intraday follow-through: 125 train trades, 0.33%
  CAGR, 0.153 Sharpe, PF 1.050 and -0.57% drop-top-five expectancy; train fail,
  validation and best-available OOS not accessed. Raw score 29, unresolved-
  survivorship-capped final score 20/100.

The data boundary now permits continued research but does not supply a
qualifying edge. Completion still requires the same frozen stocks-only rule to
show >=20% net CAGR and >=30 independent trades on the pre-frozen
best-available OOS under fixed portfolio controls and causal next-session
execution.

The latest train-only oracle-exit residual audit is explicitly lookahead and
non-scoreable. It found stable five-day-high coverage before oracle exits but
did not test a deployable exit and did not access validation/OOS. It may
motivate one frozen strength-exit hypothesis; it is not completion evidence.

That sole frozen translation (Trial 455–466) failed train with 83 trades,
0.17% CAGR, 0.085 Sharpe, PF 1.009 and -0.90% trim-five expectancy. Its raw
score was 35 and survivorship-capped final score 20/100; validation and OOS
were not accessed. The oracle-residual exit direction is therefore closed.

Trial 467–470 then tested only causal membership tenure. Fixed 90/180/365/730
calendar-day caps emitted 0/0/4/11 signals, so none met the predeclared
80-signal minimum. Trial 471–477 tested a distinct >=1% gap-up rejection then
five-session rejection-high/pivot reclaim and emitted only 27 signals across
21 symbols. Both families were closed outcome-free: no return, validation or
best-available OOS result was accessed, and neither density rule was relaxed.

Trial 478–482 then tested an orthogonal month-start allocation-flow lifecycle.
Its 143 signals passed density, but 99 train trades produced -0.32% CAGR,
-0.220 Sharpe, PF 0.750 and -0.56% trim-five expectancy. A/B/C/D were 7/7/0/0;
the normalized raw and final score were 17/100 (Reject), with disclosed
survivorship cap 20 and no-OOS/WFA cap 55. The train gate failed, so validation
and best-available OOS remained sealed.

Trial 483–488 tested a distinct 20-return lag-1 autocorrelation lifecycle.
Density passed at 129 signals and 103 train trades produced 1.29% CAGR, 0.499
Sharpe and PF 1.515, but trim-five PF/expectancy collapsed to 0.715/-0.47%.
A/B/C/D were 7/10/4/14, normalized raw 42 and final 20/100 after the disclosed
survivorship cap (the separate no-OOS/WFA cap was 55). It failed train without
opening validation or best-available OOS.

Trial 489–495 used only the repository-existing SEC Company Facts cache to
test same-accession weighted-average-share contraction. Cache coverage was
78/79 train symbols and density passed at 114 signals, but 100 trades produced
0.69% CAGR, 0.291 Sharpe, PF 1.025 and -0.57% trim-five expectancy. A/B/C/D
were 7/7/4/6, normalized raw 29 and final 20/100 after the survivorship cap;
the no-OOS/WFA cap was 55. No external data, validation or OOS was accessed.

Trial 496–504 translated a supplied strong-stock character-change checklist
into a close-confirmed, next-open exit overlay on the unchanged detection
entry. Outcome-free activation density passed at 58/103 paths, but 88 train
trades produced only 0.50% CAGR, 0.228 Sharpe, PF 0.982 and -0.87% trim-five
expectancy. A/B/C/D were 7/7/4/0, normalized raw 22 and final 20/100 after the
survivorship cap; the separate no-OOS/WFA cap was 55. The train gate failed,
so validation and best-available OOS remained sealed.

## Continue contract

Continue only with genuinely new, outcome-free-predeclared buy/sell
hypotheses. Require a density audit before return evaluation, preserve the
sequential gates, and record every negative result. Do not spend any time on
2000–2005 data and do not describe the current lack of such data as a blocker.
