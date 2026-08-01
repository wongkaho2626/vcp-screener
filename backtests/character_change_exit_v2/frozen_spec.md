# Trial 496–504 — Strong-Stock Character-Change Exit

Status: **frozen before activation counts or any return evaluation** on
2026-08-02.

## Economic hypothesis

A VCP position that has demonstrated persistent short-term trend support may
deserve more room than a generic moving-average exit. Its risk changes after
either an objectively abnormal down day or a completed loss of both the 10-
and 20-session moving averages. In the latter case, a later rally into the
formerly respected moving-average cluster that closes back below it is a
causal support-to-resistance flip. Exiting that failed recovery, or a break of
the pre-damage swing low, may retain more of a strong trend than exiting the
first moving-average breach.

This is distinct from the repository's rejected immediate SMA10/SMA20 exits,
profit targets, trailing stops and fixed three-tier scale-out. The unique
claim is the ordered state transition **strong trend -> damage -> failed
recovery / structural low break**. The baseline entry is unchanged so this is
an exit-mechanism audit, not a new entry claim.

## Frozen causal state machine

Use the unchanged PIT-filtered `detection_entry`: a completed VCP detection
schedules entry at the next session's open. For every resulting position:

1. Calculate simple 10- and 20-session moving averages using completed closes
   only. Arm `strong` once at least eight of the latest ten completed sessions
   closed strictly above both of their contemporaneous SMA10 and SMA20, with
   the current close also strictly above both averages.
2. After arming, an abnormal completed bar is either (a) an open at least 6%
   below the immediately preceding close or (b) a close-to-close loss of at
   least 16%. It schedules a full exit at the next session's open.
3. Otherwise, the first completed close strictly below both its
   contemporaneous SMA10 and SMA20 creates one `damaged` episode. Freeze the
   lower edge of that bar's SMA10/SMA20 cluster and the lowest low of the five
   completed sessions immediately before the damage bar.
4. The damage bar itself, or a later completed bar, schedules a full next-open
   exit if its close is strictly below the frozen five-session swing low.
5. During the ten sessions after damage, a failed recovery schedules a full
   next-open exit when the session high touches or exceeds the frozen lower
   edge of the SMA cluster but its close remains strictly below that lower
   edge. An abnormal bar during this window also schedules the same next-open
   exit. If none occurs, do not create another MA-damage episode for that
   position; only a later frozen swing-low break or abnormal bar can still
   activate this custom exit.
6. The existing initial hard stop and 60-session maximum hold remain in force
   and take their existing execution precedence. No partial sale, short,
   leverage, sizing, cost, liquidity or portfolio-limit change is permitted.

All indicators and state changes use only information available after the
relevant close. `model_exit_idx` is always the following session, never the
signal close. SPY remains benchmark/calendar-only.

## Deliberate omissions

No separate parabolic, hand-drawn trendline, diminishing-bounce or anchored-
price rule is encoded. Those descriptions do not define a unique reproducible
threshold, while repository work has already rejected adjacent acceleration,
PSAR and generic moving-average paths. No short setup is tested. Scaling out
is omitted because the fixed portfolio engine is full-position based and the
repository's strict scale-out experiment was already non-improving.

## Multiplicity and gates

Count nine new choices: ten-session strength window, eight qualifying closes,
the SMA10/SMA20 pair, 6% abnormal gap, 16% abnormal close loss, simultaneous
dual-MA damage, ten-session recovery window, five-session swing-low window,
and full-position exit. Declared multiplicity therefore rises from 495 to
504.

Before reading any return or outcome label, count custom exit activations on
the 2016-07-01 through 2018-06-30 train entry paths. At least 30 distinct
candidate-position activations are required; the maximum is the number of
unchanged baseline signals. This activation gate is lower than the standard
80-entry gate because the tested object is an exit overlay on an already dense
entry book. If fewer than 30 activate, close the family outcome-free without
changing a threshold.

If activation density passes, evaluate train only with unchanged sizing,
costs and constraints. The train gate remains at least 60 executed trades,
net CAGR at least 10%, Sharpe at least 0.75, profit factor at least 1.20,
positive top-five-trimmed expectancy and no fatal causality/coverage defect.
Only a train pass may open 2019–2021 validation; only its frozen 15% CAGR gate
may authorize the capped 2022–2026Q1 best-available OOS.

The unchanged detection-entry feasibility ceiling with hindsight-perfect
exits is approximately 18.72% train CAGR. Accordingly, even a successful exit
mechanism cannot by itself prove the goal's 20% OOS CAGR condition. It may only
be retained as independently supported exit evidence for a later,
predeclared joint entry/exit strategy.

No 2000–2005 data is required or permitted.
