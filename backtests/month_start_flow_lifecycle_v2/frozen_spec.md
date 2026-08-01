# Trial 478–482 — Month-Start Institutional-Flow Lifecycle

Status: **frozen before signal counts or returns** on 2026-08-01.

## Hypothesis

Regular retirement contributions, systematic allocations and benchmark flows
can create recurring demand near the start of a calendar month. An active VCP
that has already closed above its frozen pivot may provide a stocks-only way to
participate in that short flow window without chasing arbitrary breakout dates.
This calendar-flow mechanism is orthogonal to the rejected momentum, volume,
gap, moving-average and membership-tenure families.

SPY is used only as the official trading-session calendar and benchmark. It is
never eligible for an order, position or fallback.

## Frozen causal rule

For each PIT-valid active VCP setup:

1. Identify the first completed S&P 500 trading session of each calendar month
   only when the SPY date sequence contains the preceding session in a
   different month. The first bar of a truncated SPY slice is ineligible. Do
   not infer month start from a stock's possibly incomplete individual history.
2. On that completed session, require the stock's close to be strictly above
   the setup's frozen VCP pivot and not below its existing pattern stop.
3. Signal after the close and enter at the next session's open under the
   unchanged commission, slippage, sizing, cash, ten-position, name, sector,
   ADV and risk limits.
4. Schedule the model exit for the open three stock trading sessions after the
   entry open. The unchanged hard stop remains active and can exit earlier.
5. Permit at most three non-overlapping month-start entries per frozen setup.
   A later entry can occur only after the prior model exit.

The first-session calendar label is known after that session closes; no signal
uses later prices. Same-close execution is forbidden. Membership must hold on
signal and fill dates.

## Multiplicity and gates

Five declared choices raise cumulative trials from 477 to 482: first monthly
session, above-pivot state, next-open entry, three-session model exit and
three-attempt lifecycle.

Before any P&L, count discovery/train 2016-07-01 through 2018-06-30 signals.
Require 80 through 500 pre-portfolio signals. Otherwise close the family
outcome-free without changing the calendar day, hold length, pivot rule or
attempt count.

If density passes, apply the unchanged train gate: at least 60 trades, net
CAGR >=10%, Sharpe >=0.75, PF >=1.20, positive expectancy after removing the
five largest winners and no fatal integrity defect. Only a train pass opens
2019–2021 validation, where the frozen CAGR gate is >=15%. Only a validation
pass can authorise capped best-available 2022–2026Q1 OOS. Final completion
still requires >=20% net OOS CAGR and >=30 independent OOS trades.

No 2000–2005 data may be searched or used.
