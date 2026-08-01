# Trial 483–488 — Lag-1 Serial-Dependence Lifecycle

Status: **frozen before signal counts or return evaluation** on 2026-08-01.

## Economic hypothesis

Large investors commonly split orders across sessions. After a VCP has formed,
a shift in daily returns from mean-reverting or uncorrelated behaviour to
positive lag-1 serial dependence may therefore mark persistent demand. This is
mechanically different from return magnitude, moving-average slope, path
efficiency, regression trend quality, range expansion, volume accumulation and
calendar-flow rules already rejected in this repository.

## Frozen causal lifecycle

For each active PIT-valid VCP setup and every completed stock session:

1. Compute the last 20 close-to-close simple returns, ending on the current
   completed session.
2. Compute their sample Pearson lag-1 autocorrelation using the first 19
   returns as `x` and the last 19 returns as `y`. A zero-variance window is
   undefined and cannot signal.
3. Entry requires the prior session's 20-return autocorrelation to be <=0, the
   current value to be strictly >0, and the current close to be strictly above
   the frozen VCP pivot. Signal after close; fill only at the next open.
4. After entry, two consecutive completed sessions with autocorrelation <=0
   schedule a next-open model exit. The unchanged hard stop and 60-session
   timeout remain active and can exit earlier.
5. Permit at most three entries per frozen setup, with the next search starting
   only after the prior model exit.

SPY remains benchmark-only. Membership must be true on signal and fill dates.
Appending future bars must never alter an already observed signal or exit.

## Multiplicity and gates

Six declared choices increase cumulative trials from 482 to 488: 20-return
window, lag one, Pearson estimator, zero-cross entry, two-close nonpositive
exit and three-attempt lifecycle. No window, lag or threshold sweep is allowed.

First run an outcome-free 2016-07-01 through 2018-06-30 density audit. Require
80 through 500 pre-portfolio signals. Otherwise close the family without P&L
and do not relax the rule.

If density passes, apply the unchanged train gate: at least 60 executed trades,
net CAGR >=10%, Sharpe >=0.75, PF >=1.20, MDD better than -15%, positive
trim-five expectancy and no fatal integrity defect. Only a train pass opens
2019–2021 validation, whose frozen CAGR gate is >=15%. Only a validation pass
can authorise capped 2022–2026Q1 best-available OOS. Completion still requires
the same frozen strategy to achieve >=20% net OOS CAGR and >=30 independent
OOS trades.

No 2000–2005 data may be searched, reconstructed or used.
