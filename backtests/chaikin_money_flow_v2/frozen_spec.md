# Trial 358–362 — Chaikin Money Flow Reclaim Lifecycle

Status: **frozen before train or internal-holdout return evaluation** on
2026-08-01.

## Hypothesis

Prior volume rules tested isolated dry-up, breakout-volume and distribution
events. Chaikin Money Flow instead aggregates where each close occurs inside
its daily range, weighted by volume. A zero-line turn from net distribution to
net accumulation while price is above the frozen VCP pivot may identify broad
institutional sponsorship rather than one exceptional volume bar.

## Frozen causal rule

Compute 20-session CMF at every close as:

`sum(volume * ((2*close-high-low)/(high-low)), 20) / sum(volume, 20)`.

A zero multiplier is used for a zero-range bar; CMF is unavailable unless the
full 20-session window has positive total volume.

1. preceding CMF must be at or below zero and current CMF strictly above zero;
2. current close must be strictly above the setup's frozen VCP pivot;
3. fill at the next session's open;
4. exit at the next open after two consecutive later closes have CMF below
   zero;
5. require a fresh negative/non-positive-to-positive crossover after an exit,
   with at most three attempts per frozen setup.

The existing pattern hard stop and 60-session maximum hold can exit earlier.
All OHLCV and CMF inputs end at the signal/exit close. PIT membership, fixed
Edge Rank sizing, capital, position/sector/ADV constraints, 8% risk cap,
commission, slippage and all other portfolio controls remain unchanged. SPY is
benchmark-only and is not used by the signal.

The outcome-free density audit counted 4,165 train setup-day rows, 103 setups
and 88 signals before portfolio rejections; it inspected no returns.

Count the 20-session CMF, zero crossover, pivot confirmation, two-negative-CMF
exit and three-attempt lifecycle as five new multiplicity units, raising the
declared total from 357 to 362.

## Sequential gate

Train is 2016-07-01 through 2018-06-30 and requires at least 60 trades, net
CAGR >=10%, Sharpe >=0.75, PF >1.20, MDD better than -15%, and positive
expectancy after removing the five largest trades. Only a complete pass opens
the already-used 2020–2021 internal holdout, whose CAGR threshold is 15% with
the same quality gates. Formal validation and untouched OOS stay sealed
otherwise.

Report the reduced-denominator A/B/C/D raw score, all hard caps and final
capped score. A score cap is acceptable and has no minimum threshold, but the
CAGR and evidence gates remain mandatory.
