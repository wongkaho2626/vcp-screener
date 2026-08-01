# Frozen specification — detection-anchored five-day-low pullback v2

**Declared:** 2026-08-01 after train-only oracle path diagnostics and before
implementation/results. Trial 213.

## Hypothesis

On corrected adjusted-scale data, perfect train entry timing concentrates after
short-term weakness: median five-session return -1.73%, median close 2.44%
below pivot and low candle location. A causal approximation is to wait for the
first new five-session closing low after a valid VCP detection, provided the
frozen final-contraction stop still holds. This seeks a one-week pullback rather
than chasing breakout strength.

This differs from rejected MA20/pivot/Fibonacci pullbacks: it uses no moving
average, percentage retracement, breakout prerequisite or fitted price level.
It is also distinct from the unanchored RSI(2) mean-reversion family because a
current PIT VCP detection is mandatory.

## Frozen primary entry

1. Corrected adjusted-OHLC VCP detection for a PIT S&P 500 member supplies the
   as-of date, pivot and final-contraction stop. If as-of close is below stop,
   reject.
2. Starting with the first completed session after detection and for at most 60
   sessions, reject on any close below stop.
3. The first close strictly below every close in the preceding five completed
   sessions is the signal. Buy at the following open. No retry.
4. Never read `forward_outcome`.

Initial resting stop, 60-bar timeout, 5+5 bps per-side costs, USD100k capital,
Edge sizing, ten-position/name/sector/cash/ADV constraints, maximum risk and no
leverage remain fixed. SPY is benchmark-only.

## Sequential evidence gate

Train only (2016-07-01..2021-12-31). Require >=30 trades; net CAGR and Sharpe
both exceed corrected immediate-detection **and** corrected pivot-retest
baselines; PF>1.2; drop-top-5 expectancy >0. Only a complete pass permits one
validation package (2022-01-01..2026-06-30).

Validation must score >80 and net CAGR >=20%, with >=30 trades, positive
Sharpe/Sortino/Calmar, PF>1.2 and WFA efficiency >0.5 before sealed 2000-2005
OOS can be opened. PIT coverage >=90% is mandatory.

After a train pass only: prior-close lookbacks 3/10, 2x/5x/10x costs,
folds/regimes, bootstrap/Monte Carlo, trims, PSR/DSR with 213 trials, MDD and
all required metrics.
