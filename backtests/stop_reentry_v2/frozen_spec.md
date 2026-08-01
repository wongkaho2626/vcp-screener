# Frozen specification — one-time pivot-reclaim re-entry v2

**Declared:** 2026-08-01 before implementation/results. Trial 209.

## Hypothesis

The train-only feasibility audit shows that causal VCP books are chronically
underexposed and that entry filtering with the existing stop/60-bar exit cannot
approach 20% CAGR even with perfect winner selection. Some valid leaders may
shake out through the initial stop before resuming above the original pivot.
A single stateful re-entry after an actual stopout can recover that opportunity
without widening the stop, increasing size, adding leverage or repeatedly
averaging down.

This differs from the failed pre-entry pivot-reclaim rule: re-entry is permitted
only after a real portfolio position was opened and stopped. No prior VCP exit
experiment tested a one-time re-entry tied to the same frozen pivot.

## Frozen primary rules

1. Initial entry is exactly trial 206's down-close pivot-hold rule: causal
   breakout, first down-close within 10 sessions must remain strictly above the
   frozen pivot, then buy the following open.
2. Initial resting stop, costs, Edge-based size and 60-bar timeout are unchanged.
3. Only when the resting stop actually exits the position, scan that session
   and the following 19 sessions. The first completed close strictly above the
   original frozen pivot is a re-entry signal. Buy the following open.
4. Permit at most one re-entry per original signal. A second stop closes the
   trade permanently; timeout/end-of-data exits never generate re-entry.
5. Re-entry recalculates the unchanged stop as
   `max(original final-contraction low, cost-adjusted fill * 0.92)` and uses the
   same unchanged Edge Rank sizing and portfolio constraints.
6. A reclaim on the stopout session can only fill at the next session's open.
   `forward_outcome` is never read.

USD100k capital, ten-position/name/sector/cash/ADV caps, commission/slippage,
maximum risk, no-leverage rule and every non-signal portfolio setting remain
fixed. SPY is benchmark-only.

## Sequential evidence gate

Train only (2016-07-01..2021-12-31): compare against down-close pivot-hold
without re-entry. Require >=30 completed trades, net CAGR and Sharpe both above
that baseline, PF>1.2, drop-top-5 expectancy >0, and re-entry trades themselves
must have PF>1.0. Only a full pass permits one validation run
(2022-01-01..2026-06-30).

Validation must score >80 and net CAGR >=20%, with >=30 trades, positive
Sharpe/Sortino/Calmar, PF>1.2 and WFA efficiency >0.5, before sealed 2000-2005
OOS may be opened. PIT coverage >=90% is mandatory.

After a train pass only: reclaim windows 10/30 sessions, re-entry attribution,
2x/5x/10x costs, folds/regimes, bootstrap/Monte Carlo, top-winner trims,
PSR/DSR with 209 trials, MDD and the complete required metric set.
