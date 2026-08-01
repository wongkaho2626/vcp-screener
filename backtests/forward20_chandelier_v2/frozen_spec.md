# Trial 297–299 — Dense Forward-20 / Loss-Decay / Chandelier Exit

Status: **frozen before evaluating this rule** on 2026-08-01.

## Hypothesis

The p70 density trial produced enough trades but unconditional score-decay
removed productive positions together with failures. Trial 294 showed that
restricting p50 decay exits to losing positions improved the p85 result, but
the unchanged 60-session terminal price still surrendered open profit. A VCP
rule should cut failed continuation while allowing a confirmed trend to absorb
ordinary volatility. A causal chandelier exit can protect those runners
without future-path labels.

## Frozen rule

- Fit the unchanged linear ridge on the hard-stop-aware forward-20 label and
  use the unchanged purged fit/calibration chronology.
- Enter next open after the first close at or above calibration p70.
- Before a position is profitable, schedule a next-open exit when the ridge
  score is at or below calibration p50 **and** that close is below the raw
  entry open.
- Arm the chandelier only after a close reaches 10% above the raw entry open.
  Starting with the following session, track the highest close and schedule a
  next-open exit when the close is at or below highest close minus three times
  causal ATR(20).
- The fixed hard stop can exit earlier. Keep the original 60-session timeout;
  do not extend the holding period.

All portfolio sizing, cash, capacity, sector/name/ADV constraints, commissions,
slippage, 8% maximum entry risk, adjusted OHLC, point-in-time S&P 500
membership, and benchmark-only SPY are unchanged. Every score and chandelier
condition is confirmed at a close and can fill no earlier than the next open.

Count p70 dense entry, loss-only decay interaction, and the fixed chandelier as
three multiplicity units, raising the declared total 296 -> 299. Evaluate the
single compound rule once on 2020–2021. It must have at least 40 trades, CAGR at
least 15%, Sharpe at least 0.75, PF above 1.20, MDD better than -15%, and
positive drop-top-five expectancy. Failure closes the rule without formal
validation or untouched OOS.

