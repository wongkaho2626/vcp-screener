# Frozen specification — VCP pivot-retest entry v2

**Declared:** 2026-08-01, before implementing or evaluating this entry rule on
any price period. Nothing in this file may be changed after validation results
are observed. A change creates a new hypothesis and consumes a new trial.

## Hypothesis

The prior programme found that chasing breakout-day gap-ups is adversely
selected, while an MA20 pullback improves entry price but does not create
standalone alpha. A more structurally grounded entry is to require the broken
VCP pivot itself to act as support. After a causally confirmed breakout, wait
for the first bar whose low touches the frozen pivot and whose close holds at
or above it, then buy the next session's open. This should avoid extended
breakouts without adding a fitted moving-average parameter.

This is not the rejected pullback-then-rebreak rule: that rule first required
an MA20 touch and then a close above the entire post-breakout high. This rule
uses only a touch-and-hold of the original, as-of-date pivot and does not
require a new high.

## Frozen signal rule

1. Universe: stocks that were S&P 500 members on the setup's `as_of_date`,
   using `scripts/data/sp500_membership.csv`. SPY is benchmark-only and can
   never be an order candidate.
2. Setup: existing default VCP detector, with the pivot and final-contraction
   low frozen at `as_of_date`. Detector parameters are unchanged.
3. Breakout: after `as_of_date`, the first close strictly above the frozen
   pivot within the existing 60-session outcome horizon. A close below the
   frozen final-contraction low before breakout invalidates the setup.
4. Retest: during the next 15 trading sessions, the first bar satisfying
   `low <= frozen pivot <= close`. A close below the frozen
   final-contraction low before a valid retest invalidates the setup.
5. Entry: next session's open after the retest bar. The signal is therefore
   fully causal. If that open is unavailable, skip the trade.
6. Duplicate setups for a symbol follow the existing portfolio engine's
   no-double-position and strongest-Edge ordering; no discretionary choice.

There are no fitted thresholds in the primary rule: the pivot is supplied by
the setup, and the 15-session opportunity window is kept identical to frozen
v1 so only the entry reference changes.

## Fixed portfolio, risk and costs

Everything except the entry signal is held at the repository's actual frozen
portfolio implementation:

- Initial cash USD 100,000; maximum 10 concurrent positions; maximum 10% per
  name; maximum 30% per known sector; 1% of trailing 20-day ADV capacity;
  Edge Rank v2 minimum 30 and cap 82.5; unallocated capital stays cash; no
  leverage.
- Initial resting hard stop is `max(final-contraction low, fill * 0.92)`.
  A stop touch fills at `min(session open, stop)`; otherwise exit at the open
  after 60 held bars. This wording follows the engine's actual behaviour and
  supersedes the inaccurate close-confirmed wording in frozen-v1 prose.
- Commission 5 bps plus slippage 5 bps per side (10 bps combined per side),
  charged on entry and exit. Stress at 2x, 5x and 10x. No sizing, capital,
  capacity, sector, or risk-limit changes are allowed.

## Data split and untouched-OOS lock

- Discovery/train: 2016-07-01 through 2021-12-31.
- Validation: 2022-01-01 through 2026-06-30.
- Untouched OOS: 2000-01-01 through 2005-12-31. This older holdout is used
  because all 2006-2026 history has already been touched by the wider research
  programme. It remains sealed until the validation gate below passes.

Each segment must be simulated independently with its own warm-up and no
positions crossing split boundaries. Membership and price coverage must be
reported by member-day and year. Coverage below 90% blocks an uncapped score;
wrong-entity aliases and adjacent adjusted-close scale breaks are rejected.

## Validation gate before opening untouched OOS

Open the untouched OOS exactly once only if the frozen primary cell, net of
baseline costs, simultaneously has on validation:

- portfolio CAGR >= 20%;
- preliminary Backtest Score > 80 using the backtest-analyst A/B/C/D rubric;
- at least 30 independent trades;
- positive Sharpe, Sortino, Calmar, profit factor > 1.2, and no unresolved
  lookahead or survivorship hard cap;
- train and validation Sharpe have the same sign and WFA efficiency > 0.5.

If any item fails, do not inspect the untouched OOS and reject this hypothesis.
No threshold or period change is allowed in response.

## Prespecified robustness

Run on discovery/train and validation only: 2x/5x/10x cost stress; retest
window sensitivity 10 and 20 sessions (diagnostic only, never adopted);
anchored walk-forward folds; parameter-surface sign/smoothness; 10-day block
bootstrap; trade-return Monte Carlo; fold/year/regime tables; drop-top-5 and
drop-top-10 trades; PSR; DSR with **at least 194 prior trials plus this family**;
MDD, Sharpe, Sortino, Calmar, profit factor, win/payoff coherence and trade
count. The primary frozen 15-session cell alone decides the gate.

## Give-up and success criteria

- One primary validation evaluation. Reruns are allowed only for documented
  code/data defects and must preserve the spec.
- Validation gate failure closes this hypothesis without opening OOS.
- Final success requires the same frozen stocks-only rule on untouched OOS to
  retain Backtest Score >80, net CAGR >=20%, and >=30 independent trades.
- No result below those final thresholds may be described as successful.
