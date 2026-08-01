# Frozen specification — frozen-pivot limit-on-open entry v2

**Declared:** 2026-08-01 before implementation/results. Trial 215.

## Hypothesis

Corrected train oracle timing frequently enters below the VCP pivot, while
close-confirmed five-day lows and reversal entries fail. A precommitted
limit-on-open order at the structural pivot can acquire an opening-auction
pullback without using that session's high/low/close, waiting for a breakout or
fitting a retracement percentage.

This is not an intraday touch fill: the order participates only in the opening
auction, eliminating same-session high/low ordering ambiguity.

## Frozen primary entry

1. Use corrected adjusted-OHLC PIT VCP detections. Reject if as-of close is
   below the frozen final-contraction stop.
2. For the following 60 sessions, precommit a buy limit-on-open at the frozen
   pivot. Before each auction, cancel permanently if the preceding completed
   close is below stop.
3. The first opening print satisfying `stop < open <= pivot` fills at that open
   plus unchanged costs. An open at/below stop is invalid and cancels the setup;
   an open above pivot does not fill and the order may be resubmitted next day.
4. No outcome label or same-day OHLC after the opening print is consulted.

Initial resting stop, 60-bar timeout, USD100k capital, Edge sizing, max
positions/name/sector/cash/ADV/risk limits, 5+5 bps per-side costs and no
leverage remain fixed. SPY is benchmark-only.

## Sequential evidence gate

Corrected train only: >=30 trades; net CAGR and Sharpe exceed immediate-entry
and pivot-retest baselines; PF>1.2; drop-top-5 expectancy >0. Only a full pass
permits one validation package.

Validation must score >80 and net CAGR >=20%, with >=30 trades, positive
Sharpe/Sortino/Calmar, PF>1.2 and WFA efficiency >0.5 before sealed 2000-2005
OOS may be opened. PIT coverage >=90% is mandatory.

After a train pass only: order lifetimes 30/90 sessions, 2x/5x/10x costs,
folds/regimes, bootstrap/Monte Carlo, trims, PSR/DSR with 215 trials, MDD and
all required metrics.
