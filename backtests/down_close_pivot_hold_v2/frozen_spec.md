# Frozen specification — down-close pivot-hold entry v2

**Declared:** 2026-08-01 before implementation/results. Trial 206.

## Hypothesis

The first-down-close rule retained positive PF and remained marginally positive
after removing its five largest winners, but admitted deep failed-breakout
pullbacks and had worse drawdown/Sharpe than pivot-retest. A parameter-free
structural refinement is to require that the first post-breakout down-close
remain strictly above the same frozen pivot. This selects a shallow, orderly
pause without fitting a percentage retracement, moving average or volume gate.

This differs from two-close confirmation because the down-close may occur on
any of the next 10 sessions and must actually close below the prior session. It
differs from pivot-retest because no intraday touch of the pivot is required.

## Frozen primary entry

Use the exact trial-205 causal breakout and 10-session wait. The first session
that closes below its immediately preceding close is the only candidate. If it
closes at/below the frozen pivot, reject permanently; if it closes below the
pattern stop, invalidate. If it remains strictly above pivot, signal at that
close and buy the following open. No retry and no `forward_outcome` read.

All sizing, capital, maximum holdings, Edge sizing, commission/slippage,
liquidity/sector/cash constraints, initial stop and 60-bar exit remain fixed.

## Sequential evidence gate

Train only (2016-07-01..2021-12-31): >=30 trades, net CAGR and Sharpe both above
pivot-retest, PF>1.2 and drop-top-5 expectancy >0. Only a full pass permits one
validation run (2022-01-01..2026-06-30).

Validation must simultaneously score >80, net CAGR >=20%, have >=30 trades,
positive Sharpe/Sortino/Calmar, PF>1.2 and WFA efficiency >0.5 before sealed
2000-2005 OOS can be opened. PIT coverage >=90% is mandatory.

After a train pass only: wait-window sensitivity 5/15, 2x/5x/10x costs, folds,
regimes, bootstrap/Monte Carlo, trims, PSR/DSR with 206 trials, MDD and the full
required metric set.
