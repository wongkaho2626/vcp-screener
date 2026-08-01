# Frozen specification — distribution-cluster exit v2

**Declared:** 2026-08-01 before implementation/results. Trial 210.

## Hypothesis

Prior exits based on price trails, ATR, moving averages, fixed profit targets,
scale-outs and early price momentum failed. A different causal mechanism is
repeated institutional distribution: down-closes on expanding one-day volume.
A cluster of such sessions may reveal supply before either the initial stop or
60-bar timeout, while a single distribution day is ordinary noise.

No prior VCP exit experiment used a rolling count of price-and-volume
distribution events.

## Frozen primary rules

1. Entry is exactly the trial-206 down-close pivot-hold rule with next-open
   execution and frozen as-of pivot/stop.
2. After entry, a distribution session is a completed bar with
   `close < prior close` and `volume > prior volume`.
3. Maintain a trailing 15-session window. On the third distribution session in
   that window, arm a full exit and sell at the following session's open.
4. The unchanged resting hard stop is evaluated intraday before a distribution
   signal can be armed. An already armed distribution exit executes at the next
   open. The unchanged 60-bar timeout remains.
5. No same-close fill and no `forward_outcome` read.

Capital, Edge sizing, max positions, name/sector/cash/ADV limits, 5 bps
commission plus 5 bps slippage per side, maximum risk and no-leverage rule are
fixed. SPY is benchmark-only.

## Sequential evidence gate

Train only (2016-07-01..2021-12-31): compare with the same entry and baseline
exit. Require >=30 trades, net CAGR and Sharpe both higher, PF>1.2,
drop-top-5 expectancy >0, and distribution exits themselves PF>1.0. Only a full
pass permits one validation run (2022-01-01..2026-06-30).

Validation must score >80 and net CAGR >=20%, with >=30 trades, positive
Sharpe/Sortino/Calmar, PF>1.2 and WFA efficiency >0.5, before sealed 2000-2005
OOS can be opened. PIT coverage >=90% is mandatory.

After a train pass only: event counts 2/4 with the 15-session window, window
10/20 with count 3, 2x/5x/10x costs, folds/regimes, bootstrap/Monte Carlo,
trims, PSR/DSR with 210 trials, MDD and all required metrics.
