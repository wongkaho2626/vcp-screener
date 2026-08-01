# Frozen specification — post-breakout inside-day entry v2

**Declared:** 2026-08-01 before implementation/results. Trial 208.

## Hypothesis

After a causal VCP breakout, a strict inside day (lower high and higher low than
the prior session) is a fresh, directly observed contraction in volatility. If
that pause still closes above the frozen pivot, it may identify orderly supply
absorption without chasing the breakout or fitting a retracement threshold.

This differs from the pattern-level contraction filters already rejected: it
uses a new post-breakout two-bar event. It differs from pivot-retest and first
down-close rules because no pivot touch or red close is required.

## Frozen primary entry

1. Use default PIT VCP detection and the frozen pivot/final-contraction low.
2. Find the first post-detection close above pivot within the existing causal
   60-session horizon; a prior close below stop invalidates.
3. In the next 10 sessions, locate the first strict inside day:
   `high < prior high` and `low > prior low`. A close below stop invalidates.
4. The first inside day must close strictly above pivot. Otherwise reject with
   no retry. If it holds, signal at its close and buy the following open.
5. Never read `forward_outcome`.

Capital, Edge sizing, max holdings, commissions/slippage, initial stop, 60-bar
exit, cash/sector/ADV constraints and all risk settings remain fixed.

## Sequential evidence gate

Train only (2016-07-01..2021-12-31): >=30 trades, net CAGR and Sharpe both above
pivot-retest, PF>1.2, drop-top-5 expectancy >0. Only a full pass permits one
validation run (2022-01-01..2026-06-30).

Validation must score >80 and net CAGR >=20%, with >=30 trades, positive
Sharpe/Sortino/Calmar, PF>1.2 and WFA efficiency >0.5, before opening sealed
2000-2005 OOS. PIT coverage >=90% is mandatory.

After a train pass only: 5/15-session windows, 2x/5x/10x costs, folds/regimes,
bootstrap/Monte Carlo, trims, PSR/DSR with 208 trials, MDD and all required
metrics.
