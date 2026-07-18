# PIT replay addendum — frozen before any PIT result was computed

**Declared:** 2026-07-18, after the survivor-only result (paired Δ +0.688,
t 2.50) but before any delisted-inclusive detection or trade was computed.

## Purpose

Lift (or honestly re-measure) the survivorship cap by replaying the
**unchanged** frozen spec (`frozen_spec.md`) on a delisted-inclusive
point-in-time universe. No rule, parameter, fold, trim, or metric changes.

## Data protocol

1. Universe: all tickers with S&P 500 membership overlapping 2006-01-01 …
   2015-12-31 per `scripts/data/sp500_membership.csv` (fja05680 dataset,
   735 tickers).
2. Prices: existing CSV series for the 339 survivors, plus every missing
   member recoverable from Yahoo (window 2004-01-01 … 2016-12-31), with a
   membership-overlap guard that rejects series whose bars do not intersect
   the ticker's membership interval (anti ticker-reuse). Unrecoverable names
   are recorded, with member-day coverage quantified; no synthetic filling.
3. Detection: `backtest_vcp.py` frozen defaults on the PIT CSV truncated at
   2015-12-31 (same anchor as round 1).
4. **Membership gate (the only new mechanism, declared here):** a detection
   counts only if the symbol was an index member on its `as_of_date`
   (causal; membership is public information on that date). Implemented as a
   post-filter in `pullback_oos_experiment.py --membership-csv`, mirroring
   `trade_simulator.py`'s existing flag.
5. Simulation: untruncated PIT CSV so late-2015 entries can exit into 2016.
   Benchmark: synthetic equal-weight of the PIT CSV universe (now includes
   delisted names — a more honest benchmark than round 1's survivors-only).

## Declared outcomes (unchanged from frozen_spec.md)

Primary: paired Δ > 0, t ≥ 2 pooled; same sign both folds; trim signs hold.
The PIT replay supersedes the survivor-only run for scoring purposes. If the
effect dies on PIT data, that is the result — the survivor-only "pass" is
then attributed to survivorship, recorded as such, and the experiment closes
as a failure to replicate. No re-tuning in either case.

## Coverage honesty rule

The survivorship cap is considered *lifted* only if recovered member-day
coverage ≥ 90% and the unrecovered names are not concentrated in
crisis-era delistings; between 70-90% the cap is *partially mitigated*
(score capped at the no-walk-forward tier, 55, at best); below 70% the cap
stands. Coverage is computed as covered member-trading-days / total
member-trading-days over 2006-2015, and reported per year.
