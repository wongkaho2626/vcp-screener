# Frozen specification — five-day-low reversal confirmation v2

**Declared:** 2026-08-01 before implementation/results. Trial 214.

## Hypothesis

Trial 213 confirmed that buying every first five-day closing low admits too many
falling knives. A short-term reversal becomes observable only when demand later
closes above the entire low bar. Requiring that structural recovery should keep
the oracle-motivated pullback anchor while rejecting lows that continue lower.

This differs from the rejected pivot-retest-high confirmation: the reference
bar is a post-detection five-session closing low, not a pivot touch after a
breakout. No MA, percentage retracement, volume threshold or future label is
used.

## Frozen primary entry

1. Use corrected adjusted-OHLC PIT VCP detections and immediate as-of stop
   invalidation.
2. Within 60 sessions, locate the first close strictly below the preceding five
   closes while still at/above the frozen final-contraction stop.
3. Freeze that low bar's high. During the following three sessions, reject on a
   close below the pattern stop; otherwise the first close strictly above the
   frozen low-bar high is the reversal signal. No confirmation means reject.
4. Buy the following open; no retry and no `forward_outcome` read.

Initial stop, 60-bar timeout, costs, USD100k capital, Edge sizing, max
positions/name/sector/cash/ADV/risk constraints and no leverage remain fixed.
SPY is benchmark-only.

## Sequential evidence gate

Corrected train only (2016-07-01..2021-12-31): >=30 trades; CAGR and Sharpe
both above immediate-detection and pivot-retest baselines; PF>1.2; drop-top-5
expectancy >0. Only a complete pass permits one validation package.

Validation must score >80 and net CAGR >=20%, with >=30 trades, positive
Sharpe/Sortino/Calmar, PF>1.2 and WFA efficiency >0.5 before sealed 2000-2005
OOS may be opened. PIT coverage >=90% is mandatory.

After a train pass only: confirmation windows 2/5, 2x/5x/10x costs,
folds/regimes, bootstrap/Monte Carlo, trims, PSR/DSR with 214 trials, MDD and
all required metrics.
