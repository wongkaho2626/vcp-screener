# Frozen specification — failed-breakout pivot reclaim v2

**Declared:** 2026-08-01 before implementation/results. Trial 207.

## Hypothesis

A VCP breakout that closes back under its frozen pivot but remains above the
final-contraction low may represent a shakeout rather than structural failure.
A prompt close back above that same pivot supplies a causal recovery signal and
avoids buying both the initial breakout premium and an unrecovered breakdown.

This differs from pivot-retest because it requires a close at/below pivot before
the reclaim. It differs from the rejected MA/rebreak rule because it does not
use an MA touch or require a close above the post-breakout high.

## Frozen primary entry

1. Use the default point-in-time VCP detection, frozen pivot and final-
   contraction low for a point-in-time S&P 500 member.
2. Find the first post-detection close strictly above pivot within the existing
   causal 60-session horizon. Any earlier close below the stop invalidates.
3. In the next 15 sessions, wait for the first close at/below pivot but at/above
   the pattern stop. A close below stop invalidates.
4. In the next 5 sessions after that undercut, the first close strictly above
   pivot is the reclaim signal. A close below stop invalidates; no reclaim means
   rejection and there is no retry.
5. Buy the following open. Never read `forward_outcome`.

All sizing, capital, holding limit, Edge sizing, commission/slippage, stop,
60-bar time exit, cash/sector/ADV constraints and risk rules remain fixed.

## Sequential evidence gate

Train only (2016-07-01..2021-12-31): >=30 trades, net CAGR and Sharpe above
pivot-retest, PF>1.2 and drop-top-5 expectancy >0. Only a complete pass permits
one validation run (2022-01-01..2026-06-30).

Validation must score >80 and net CAGR >=20%, with >=30 trades, positive
Sharpe/Sortino/Calmar, PF>1.2 and WFA efficiency >0.5, before sealed 2000-2005
OOS can be opened. PIT member-day coverage must be >=90%.

After a train pass only: neighbouring (10,3) and (20,7) undercut/reclaim
windows, 2x/5x/10x costs, folds/regimes, bootstrap/Monte Carlo, trims, PSR/DSR
with 207 trials, MDD and all required metrics.
