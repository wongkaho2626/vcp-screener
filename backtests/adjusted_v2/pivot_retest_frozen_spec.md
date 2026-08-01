# Corrected adjusted-scale pivot-retest baseline — frozen remeasurement

**Declared:** 2026-08-01 after train-only scale audit and before corrected
validation. Trial 212.

This is not a newly selected rule. It remeasures the previously frozen
pivot-retest specification after fixing the raw-vs-adjusted OHLC correctness
bug. Entry remains: first causal post-detection close above the frozen adjusted
pivot; within 15 sessions, first `low <= pivot <= close`; buy following open.
As required by the original prose, a setup whose adjusted as-of close is already
below the adjusted final-contraction stop is invalid immediately.

Portfolio capital, Edge sizing, max positions, name/sector/cash/ADV limits,
resting stop, 60-bar timeout, 5+5 bps per-side costs and no leverage remain
fixed. PIT S&P 500 membership is enforced and SPY is benchmark-only.

Train-only audit (2016-07-01..2021-12-31) observed 85 admitted trades and 0.95%
net CAGR. Because this is the mandatory corrected baseline remeasurement rather
than a promoted post-hoc cell, run one validation package on
2022-01-01..2026-06-30 with 10/20-session sensitivity, 2x/5x/10x costs,
bootstrap/Monte Carlo, PSR/DSR using 212 trials, trims and full risk metrics.

Only validation Score >80, net CAGR >=20%, >=30 trades, positive
Sharpe/Sortino/Calmar, PF>1.2 and WFA efficiency >0.5 may open sealed 2000-2005
OOS. No corrected-validation failure can be described as success.
