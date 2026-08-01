# Trial 489–495 — SEC Share-Supply Contraction Lifecycle

Status: **frozen before coverage counts, signal density or returns** on
2026-08-01.

## Economic hypothesis and interpretation limit

A year-over-year decline in weighted-average shares can indicate that net
repurchases exceed issuance. Reduced share supply may support a VCP continuation
after the information becomes public in a 10-Q or 10-K. The measure is only a
share-supply contraction proxy: acquisitions, capital structure changes and
other events can also alter weighted-average shares, so the experiment must not
label every observation a buyback.

This mechanism is distinct from the repository's prior EPS/revenue growth,
margin, cash conversion, Form 4 insider purchase, technical volume and price-
serial-dependence experiments. It uses only Company Facts JSON already cached
before the current 2006+ goal.

## Frozen point-in-time event

For each 10-Q or 10-K accession, compare the current and roughly year-earlier
duration-matched weighted-average share values presented in that same accession.
Prefer `WeightedAverageNumberOfDilutedSharesOutstanding`; fall back to
`WeightedAverageNumberOfSharesOutstandingBasic` only when diluted comparison is
unavailable. The current and prior values must both be positive.

An event is eligible only when:

- its SEC `filed` date is strictly earlier than the completed signal date;
- it is the latest eligible share-count filing for that stock;
- it is no more than 120 calendar days old; and
- current shares / prior shares - 1 is strictly below zero.

A same-day filing cannot signal. A later non-contraction filing supersedes an
older contraction; there is no cherry-picking among historical filings.

## Frozen causal lifecycle

1. While a PIT-member VCP setup remains active, require the eligible share-
   supply contraction state and a completed close strictly above the frozen
   pivot.
2. Signal after that close and fill no earlier than the next open, under the
   unchanged costs, sizing, capital, position, sector, name, ADV and risk
   limits.
3. Schedule a model exit at the open 20 stock sessions after entry. The
   unchanged hard stop remains active and can exit first.
4. After the model exit, allow another entry only if the then-latest filing is
   still a fresh contraction and the close remains above pivot. Permit at most
   three entries per frozen setup.

SPY is benchmark-only. Membership must hold on signal and fill dates. Future
filings or bars cannot alter an already emitted signal.

## Multiplicity and gates

Seven declared choices raise cumulative trials from 488 to 495: same-accession
comparison, diluted-before-basic tag priority, strict negative growth threshold,
120-day freshness, above-pivot entry, 20-session exit and three-attempt
lifecycle. No share-growth threshold, freshness or holding-period sweep is
allowed.

First audit 2016-07-01 through 2018-06-30 without any outcome labels or P&L.
Require 80 through 500 pre-portfolio signals. If density fails, close the family
outcome-free without loosening any rule.

If density passes, apply the unchanged train gate: at least 60 trades, net CAGR
>=10%, Sharpe >=0.75, PF >=1.20, MDD better than -15%, positive trim-five
expectancy and no fatal integrity defect. Only a train pass opens 2019–2021
validation; only its frozen >=15% CAGR pass may authorise capped 2022–2026Q1
best-available OOS. Completion still requires >=20% net OOS CAGR and >=30
independent OOS trades for the same frozen rule.

No 2000–2005 data may be searched, reconstructed or used.
