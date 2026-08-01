# Frozen specification — two-close breakout confirmation v2

**Declared:** 2026-08-01 before implementation/results. Trial 204.

## Hypothesis

A single close above the VCP pivot is vulnerable to a one-day false breakout.
Two consecutive post-detection closes strictly above the same frozen pivot
show persistent demand without waiting for a retracement or chasing a later
new high. Entering at the open after the second close should increase sample
and exposure versus pivot-retest while rejecting immediate breakout failures.

This differs from the rejected pullback-rebreak rule: no MA touch, pullback or
post-breakout-high break is required. It also differs from latency conditioning:
the condition is persistence above a structural price, not calendar freshness.

## Frozen entry

1. Point-in-time S&P 500 member on VCP `as_of_date`; default detector and
   frozen pivot/final-contraction low unchanged.
2. Walk post-detection bars causally. The first close above pivot is close #1.
3. The immediately following trading session must also close strictly above
   pivot. If it closes below the pattern stop, invalidate; if it merely closes
   at/below pivot, reject the setup (no later retry).
4. Buy at the next session's open. `forward_outcome` is never read.
5. Existing initial stop, 60-bar exit, costs, USD100k capital, Edge sizing,
   maximum positions, cash, sector/name/ADV constraints stay fixed.

## Sequential evidence gate

Train only: 2016-07-01..2021-12-31. Proceed to one validation run only if
>=30 trades, net CAGR and Sharpe both exceed pivot-retest baseline, PF>1.2,
and drop-top-5 expectancy >0. Validation: 2022-01-01..2026-06-30.

Only if validation simultaneously achieves score >80, net CAGR >=20%, >=30
trades, positive Sharpe/Sortino/Calmar, PF>1.2 and WFA efficiency >0.5 may the
sealed 2000-2005 OOS be opened. PIT coverage >=90% required throughout.

Prespecified diagnostics after a train pass: three consecutive closes and a
one-close baseline as sensitivity only; 2x/5x/10x costs, folds, bootstrap/
Monte Carlo, trims, PSR/DSR using 204 trials and full risk/trade metrics.
