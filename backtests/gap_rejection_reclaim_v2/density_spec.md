# Trial 471–477 — Gap-Rejection Supply-Absorption Reclaim

Status: **frozen before signal counts or any return evaluation** on 2026-08-01.

## Economic hypothesis

The repository's earlier entry-day gap study found that immediately chasing a
gap-up was adversely selected. A different, causal mechanism is possible: a
gap-up can initially meet visible supply and close below its open, while a
later close above that rejection bar's high shows that the supply was absorbed.
Waiting for that reclaim may separate proven continuation from the rejected
gap-chasing rule.

This is not a generic gap direction, intraday-return decomposition, five-day-
low reversal or pivot-only reclaim. Both the gap rejection and the later
reclaim of its frozen high are required.

## Frozen causal lifecycle

For each active PIT-member VCP setup in discovery/train 2016-07-01 through
2018-06-30:

1. A rejection bar opens at least 1.00% above the immediately preceding close
   and closes strictly below its own open.
2. Freeze that completed bar's high and low. During the next five trading
   sessions, require the first close strictly above both the frozen rejection
   high and the setup's frozen VCP pivot.
3. That reclaim close is the signal; entry is at the next session's open with
   the unchanged costs, sizing, portfolio limits and liquidity/risk controls.
4. A later close below the frozen rejection low schedules a next-open model
   exit. The unchanged initial hard stop and 60-session maximum hold remain in
   force and can exit earlier.
5. After such an exit, the lifecycle can search for another complete rejection
   and reclaim. Allow at most three entries per frozen setup. A setup becomes
   invalid when its existing pattern stop is breached.

Every decision uses only completed bars. The signal bar can never fill at its
own close. SPY is benchmark-only and membership must be valid on signal and
fill dates.

## Multiplicity and outcome-free density gate

Count seven declared choices: 1% gap threshold, bearish rejection close,
five-session reclaim window, strict rejection-high reclaim, frozen-pivot
confirmation, rejection-low failure exit and three-attempt lifecycle. This
raises declared trials from 470 to 477.

Before any return, outcome label, validation or best-available OOS access,
count pre-portfolio train signals. The family may proceed to a separately
frozen return specification only with 80 through 500 signals. If it produces
fewer than 80 or more than 500, close the family outcome-free. Thresholds,
window and attempt count may not be relaxed after the count is observed.

If density passes, the later train gate remains unchanged: at least 60
executed trades, net CAGR at least 10%, Sharpe at least 0.75, PF at least 1.20,
positive trim-five expectancy and no fatal causality/coverage defect. Only a
train pass may open 2019–2021 validation; only a validation pass at its frozen
15% CAGR gate may authorise the capped 2022–2026Q1 best-available OOS.

No 2000–2005 data is required or permitted for this experiment.
