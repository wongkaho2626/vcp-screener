# Frozen specification — first post-breakout down-close entry v2

**Declared:** 2026-08-01 before implementation/results. Trial 205.

## Hypothesis

Immediate and persistent-breakout entries pay the short-lived breakout-day
premium, while the MA20 and exact-pivot retest rules can wait for an unusually
deep pullback. The first ordinary down-close after a causal breakout is a
parameter-light compromise: it waits for the first pause in demand without
requiring a specific moving average, retracement percentage or later new high.

This has not been tested by the prior latency, MA pullback, pivot-retest,
rebreak, Fibonacci, gap or two-close experiments. It is an entry-timing rule,
not a fitted score/volume/trend gate.

## Frozen primary entry

1. The default point-in-time VCP detector supplies an as-of-date pivot and
   final-contraction low for a point-in-time S&P 500 member.
2. Starting strictly after detection, find the first close strictly above the
   frozen pivot within the existing 60-session causal breakout horizon. A
   prior close below the pattern stop invalidates the setup.
3. During the next 10 trading sessions, reject on the first close below the
   pattern stop. Otherwise, the first session whose close is strictly below
   the immediately preceding session's close is the signal bar.
4. Buy at the following session's open. No retry and no `forward_outcome` read.
5. Existing initial stop, 60-bar exit, costs, USD100k capital, Edge sizing,
   position/cash/sector/ADV limits and all other risk rules remain unchanged.

## Sequential evidence gate

Train only: 2016-07-01..2021-12-31. Compare with the frozen pivot-retest entry.
Proceed to exactly one validation run only if the candidate has >=30 trades,
net CAGR and Sharpe both above pivot-retest, PF>1.2, and drop-top-5 expectancy
>0. Validation is 2022-01-01..2026-06-30.

Only if validation simultaneously produces Backtest Score >80, net CAGR >=20%,
>=30 trades, positive Sharpe/Sortino/Calmar, PF>1.2 and WFA efficiency >0.5 may
the sealed 2000-2005 OOS be opened. PIT member-day coverage must remain >=90%.

Prespecified sensitivity after a train pass only: 5- and 15-session wait
windows. Then 2x/5x/10x costs, folds/regimes, bootstrap/Monte Carlo, top-winner
trims, PSR/DSR with 205 trials, MDD and all required performance metrics.
