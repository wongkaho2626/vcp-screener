# Trial 296 — SEC Dual-Growth / Forward-20 Timing

Status: **frozen before evaluating this rule on return outcomes** on 2026-08-01.

## Hypothesis

Trial 288 showed that the forward-20 ridge identifies robust opportunities but
has too little exposure at p85. Trials 289–291 showed that lowering the score
threshold alone adds low-quality trades. A genuinely orthogonal, strictly
point-in-time catalyst may separate productive technical continuation from the
extra p70 candidates: recent as-filed acceleration in both diluted EPS and
revenue.

## Fixed entry and exit

Retain the Trial 288 forward-20 ridge, fit chronology, lambda=10, fifteen causal
technical features, and outcome-free calibration distribution. Enter at the
next open after the first setup close that simultaneously satisfies:

- ridge score at or above the already-defined calibration p70 threshold;
- latest comparable SEC 10-Q/10-K has `filed < signal_date` and is no more than
  120 calendar days old;
- diluted EPS YoY growth is at least 20%; and
- revenue YoY growth is at least 10%.

EPS and revenue comparisons must use current and prior-period facts presented
within the same accession. Missing or non-comparable facts fail closed. Do not
use fiscal facts from an accession filed on or after the signal date. After
entry, exit next open on the original p50 ridge score-decay rule; the unchanged
hard stop and 60-session timeout can exit earlier. A later filing is allowed to
affect a later entry only after its filing date, but is not required for exit.

## Controls and decision gate

Keep point-in-time S&P 500 membership, adjusted OHLC, next-session execution,
portfolio sizing, initial cash, ten-position cap, name/sector/ADV limits, 8%
risk cap, commissions, slippage, and all other portfolio restrictions fixed.
SPY remains benchmark-only.

This is one prespecified interaction rule, taking declared multiplicity from
295 to 296. Evaluate it once on the 2020–2021 internal holdout. It must produce
at least 25 trades, CAGR at least 15%, Sharpe at least 0.75, profit factor above
1.20, maximum drawdown better than -15%, and positive expectancy after removing
the five largest winners. Failure closes the rule without accessing formal
validation or untouched OOS.

