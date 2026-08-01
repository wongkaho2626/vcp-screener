# Exploratory Existing-Data Replay — Trial 288

**Declared:** 2026-08-01, before generating post-2021 daily detections or
inspecting any 2022–2026 strategy outcome.

## Classification

This run follows the user's instruction to use the data already present in the
workspace despite its survivorship limitation. It is explicitly
**exploratory and non-qualifying**:

- it does not relabel 2022–2026 as untouched OOS;
- it cannot authorise formal validation or goal completion;
- both the raw Backtest Score and the rubric score after applicable hard caps
  must be reported;
- the original goal's >80 Score, >=20% net CAGR and >=30 independent untouched
  OOS trades requirements remain unchanged.

The purpose is narrower: measure how the strongest causal internal candidate
behaves in the later portion of the available PIT reconstruction without
changing the strategy.

## Frozen strategy

Replay Trial 288 exactly:

1. Daily causal VCP detections from the corrected adjusted-OHLC detector,
   stride one, no support/resistance overlay.
2. Fit period 2016-07-01 through 2018-06-30, with prices through 2018-09-30.
3. Same fifteen causal daily state features, setup-equal weighted linear ridge
   with lambda=10, and hard-stop-aware forward-20 labels clipped to
   [-20%, +50%].
4. Outcome-free threshold calibration on 2019-01-01 through 2019-06-30, with
   prices through 2019-09-30: p85 entry and p50 exit.
5. Enter only at the next open following a close-confirmed score at or above
   p85. Exit only at the next open following later score decay to or below p50,
   or earlier via the unchanged hard stop; retain the 60-session timeout.
6. Preserve the repository's capital, position sizing, cash constraint,
   maximum holdings, name/sector/ADV constraints, 8% entry-risk cap,
   commission and slippage. No leverage. SPY remains benchmark-only.

## Frozen exploratory evaluation

- Evaluation signals: 2022-01-01 through **2026-03-31**.
- Available prices end 2026-07-01, leaving about 60 trading sessions after the
  final signal date for causal exit completion.
- PIT membership must be true on both signal and fill dates.
- Source coverage report: 91.31% overall; per-year coverage rises from 93.7%
  in 2022 to 98.7% in 2026. Missing members and delisted observations remain a
  confirmed limitation.
- No alternative threshold, feature, exit, subperiod or endpoint will be
  evaluated after seeing the result.

## Pre-outcome integrity amendment: benchmark date alignment

The first full-history detector build was followed only by a 2020–2021 parity
control; no 2022–2026 strategy outcome was opened. Although fit and calibration
row counts matched Trial 288, its fitted coefficients and thresholds changed.
The audit traced this to a detector defect: historical analysis sliced SPY by
the stock's integer bar offset. Short histories, halts and missing stock bars
therefore compared against the wrong SPY date and could include a post-as-of
benchmark bar. Appending later input rows also changed the historical RS value.

Before opening the exploratory evaluation, the scanner is amended to align SPY
by calendar date (`benchmark_date <= stock_as_of_date`) and a regression test
proves that no future benchmark bar enters historical relative strength. The
full detector must be regenerated and the frozen Trial 288 model refitted using
the same periods, features, lambda and outcome-free percentile rules above.
The old Trial 288 threshold is not forced onto changed causal features. This is
an execution-integrity correction, not a parameter choice; no outcome-dependent
alternative is permitted.

## Prespecified diagnostics

Report net CAGR, total return, MDD, Sharpe, Sortino, Calmar, profit factor,
expectancy, win/payoff mix, trade count, PSR, DSR/multiplicity treatment,
effective sample size, daily distribution/autocorrelation tests, monthly and
year/fold consistency, cost stress at 1x/2x/5x/10x, drop-top-five and
drop-top-ten trades, block/bootstrap or trade Monte Carlo intervals, and the
Backtest Score component breakdown with every applicable cap.
