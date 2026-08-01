# Trial 313–315 — P70 Prove-It / Reset Lifecycle

Status: **frozen before evaluating this rule** on 2026-08-01.

## Hypothesis

P70 entries provide adequate density but include many failed continuations.
The prior p85 lifecycle waited only for score decay, and the prior managed exit
removed positions whose *highest* close failed a +2% test. A less destructive
state machine should exit only positions still underwater after five completed
sessions, then require an observable low-score reset before another attempt.
This can recycle a valid VCP setup without stacking positions or changing size.

Use the original Trial 288 forward-20 linear ridge, fit chronology, lambda=10,
fifteen causal features, and outcome-free calibration distribution:

1. enter next open after score first reaches calibration p70;
2. after the fifth holding-session close, exit next open if that close is below
   the raw entry open;
3. an earlier/later p50 score-decay close also exits next open;
4. after an exit, require a later score at or below p50, then a later p70
   crossing before re-entry;
5. require at least five sessions between entries and allow at most three
   attempts per frozen setup.

The unchanged hard stop and 60-session timeout may exit earlier. Every state
transition is close-confirmed and fills no earlier than the next open. PIT S&P
500 membership, adjusted OHLC, fixed cash/sizing/capacity, name/sector/ADV
constraints, 8% risk cap, costs, and benchmark-only SPY remain fixed.

Count the five-session underwater check, reset-required re-entry, and maximum
three attempts as three multiplicity units, raising 312 -> 315.

Because 2020–2021 has already been used extensively, it is discovery—not
formal validation—for this new rule. It needs at least 80 trades, CAGR at least
10%, Sharpe at least 0.75, PF above 1.20, MDD better than -15%, and positive
drop-top-five expectancy. Failure closes the rule. A pass permits a separate
unchanged specification to be frozen before accessing 2022–2026 validation;
untouched 2000–2005 OOS remains sealed.

