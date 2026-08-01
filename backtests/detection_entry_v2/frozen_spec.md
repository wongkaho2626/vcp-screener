# Frozen specification — immediate post-detection entry v2

**Declared:** 2026-08-01, before implementing or evaluating this entry rule.
This is trial 196. Nothing below changes after validation results are seen.

## Hypothesis

Every prior implementation waits for a breakout or a later momentum/retest
event. That creates adverse selection at extended prices and leaves the fixed
portfolio mostly in cash. A default VCP detection is already a fully formed,
Stage-2 candidate near a frozen pivot with a defined contraction-low risk
point. Entering at the next open immediately after `as_of_date` should capture
the pre-breakout risk/reward and increase opportunity without changing sizing,
leverage, portfolio caps or detector parameters.

This is a new timing rule, not a resurrection of failed breakout gates: it
does not filter on score, RS, volume, trend, gap, duration, contraction ratio,
or future breakout outcome.

## Frozen buy signal

1. Point-in-time S&P 500 member on `as_of_date`; SPY benchmark-only.
2. Existing default VCP detection and detector parameters unchanged.
3. Signal is the detection close itself. Buy at the next available session's
   open. `forward_outcome` and every later bar are forbidden in signal logic.
4. Repeated detections follow the unchanged no-double-position and
   strongest-Edge ordering in the existing portfolio engine.

## Fixed portfolio, exits and costs

Identical to frozen v1 and pivot-retest v2 actual engine: USD100,000 cash,
maximum 10 positions, 10% name cap, 30% known-sector cap, 1% trailing-20-day
ADV cap, unchanged Edge Rank minimum/cap, no leverage; resting initial stop at
`max(final-contraction low, fill*0.92)` with gap-through handling; 60-bar time
exit; 5 bps commission plus 5 bps slippage per side. Stress 2x/5x/10x.

## Split, gate and untouched lock

- Discovery/train: 2016-07-01 through 2021-12-31.
- Validation: 2022-01-01 through 2026-06-30.
- Untouched OOS: 2000-01-01 through 2005-12-31, sealed unless validation
  simultaneously achieves net CAGR >=20%, preliminary Backtest Score >80,
  >=30 trades, positive Sharpe/Sortino/Calmar, PF>1.2, and train/validation
  same-sign Sharpe with efficiency >0.5.
- PIT coverage must be >=90%; segments run independently with no crossing
  positions. One primary evaluation; reruns only for documented bugs.

## Prespecified robustness and success

Primary rule has no tunable entry parameter. Report anchored chronological
folds, 2x/5x/10x costs, 10-day block bootstrap, trade Monte Carlo, year/regime,
drop-top-5/10, PSR, DSR at 196 trials, MDD, Sharpe, Sortino, Calmar, PF and
trade count. A diagnostic one-session delay (enter second open after detection)
tests timing fragility and can never replace the primary cell.

Validation failure closes the hypothesis without opening OOS. Final success
requires the same frozen rule on untouched OOS to retain score >80, net CAGR
>=20%, and >=30 independent trades. Lower results are failures.
