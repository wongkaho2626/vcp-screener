# Frozen specification — loss-only distribution-cluster exit v2

**Declared:** 2026-08-01 before implementation/results. Trial 211.

## Hypothesis

Trial 210's distribution-cluster exits were individually profitable and reduced
drawdown, but firing on profitable positions truncated the long right tail and
cut CAGR. Institutional distribution is more actionable when the position is
also below its cost-adjusted entry: this identifies a laggard with both adverse
price state and expanding-volume sell pressure, while leaving profitable
leaders under the load-bearing 60-bar exit.

This is not the rejected fixed-day price cull: there is no day-10/15 return
threshold. Exit requires three causal price-and-volume distribution events.

## Frozen primary rules

Use the exact down-close pivot-hold entry and exact trial-210 rolling definition
(three down-close/higher-volume events within 15 sessions). On the third or any
later qualifying distribution event while the completed close is strictly
below the cost-adjusted entry price, arm a full exit for the following open.
Clusters while at/above entry do not exit and remain eligible for a later
qualifying distribution event. Resting stop priority and 60-bar timeout remain.

All sizing, capital, max positions, costs, initial stop/risk, cash/sector/ADV
constraints and no-leverage rule are fixed. SPY is benchmark-only and
`forward_outcome` is never read.

## Sequential evidence gate

Train only (2016-07-01..2021-12-31): compare with the same entry and baseline
exit. Require >=30 trades, higher net CAGR and Sharpe, PF>1.2, drop-top-5
expectancy >0, and loss-distribution exits PF>1.0. Only a full pass permits one
validation run (2022-01-01..2026-06-30).

Validation must score >80 and net CAGR >=20%, with >=30 trades, positive
Sharpe/Sortino/Calmar, PF>1.2 and WFA efficiency >0.5, before sealed 2000-2005
OOS can be opened. PIT coverage >=90% is mandatory.

After a train pass only: event counts 2/4, windows 10/20, 2x/5x/10x costs,
folds/regimes, bootstrap/Monte Carlo, trims, PSR/DSR with 211 trials, MDD and
the complete required metric set.
