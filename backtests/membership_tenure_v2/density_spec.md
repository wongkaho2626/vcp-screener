# Trial 467–470 — PIT Membership-Tenure Density Audit

Status: **frozen before signal counts or any return evaluation** on 2026-08-01.

## Hypothesis and causal boundary

Earlier point-in-time momentum work showed that much of the apparent survivor-
only momentum edge was associated with index inclusion. A newly included S&P
500 company may experience forced-index demand, greater institutional coverage
and a transition in its shareholder base. VCP opportunities early in the
current membership spell could therefore differ from long-tenured members.

Only the start date of the membership interval containing the signal date is a
feature. The interval end date may be used solely to verify that both signal and
fill occurred while the stock was a member; it is never exposed to the signal,
ranking or threshold. Calendar-day tenure is non-negative and fully known on
the signal date. SPY is excluded.

## Outcome-free density grid

Start from the unchanged causal detection-entry candidates in discovery/train
2016-07-01 through 2018-06-30, using prices through the embargo only to permit
next-open fills and ordinary bookkeeping. Require signal and fill to belong to
the same historical membership interval. Count candidates whose tenure on the
signal date is no more than each fixed cap:

- 90 calendar days;
- 180 calendar days;
- 365 calendar days;
- 730 calendar days.

No return, outcome label, exit path, validation or OOS data may be read. Each
cap is one multiplicity unit, increasing declared trials from 466 to 470.

## Selection and give-up rule

A strategy specification may be created only if a cap has 80 through 500
pre-portfolio candidates. Select the **shortest** cap meeting that unchanged
density range; do not select by performance. If none qualifies, close the
membership-tenure family outcome-free. If one qualifies, the later strategy
must freeze entry/exit, multiplicity, train/validation gates and all portfolio
controls before evaluating returns.

Missing 2000–2005 data is out of scope. No external data may be searched or
added for this audit.
